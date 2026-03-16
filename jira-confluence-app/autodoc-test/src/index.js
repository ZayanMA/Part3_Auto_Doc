import Resolver from '@forge/resolver';
import api, { route, storage } from '@forge/api';
import crypto from 'node:crypto';

const resolver = new Resolver();

// ─── Constants ────────────────────────────────────────────────────────────────

const KIND_PAGE_TITLES = {
  api: 'API',
  models: 'Models',
  config: 'Config',
  cli: 'CLI',
  tests: 'Tests',
  module: 'Modules',
};

// ─── Issue Panel: fetch linked AutoDoc pages for a Jira issue ────────────────

resolver.define('fetchLinkedDocs', async (req) => {
  const key = req.context.extension.issue.key;

  const res = await api.asApp().requestJira(
    route`/rest/api/3/issue/${key}/remotelink`,
    { headers: { Accept: 'application/json' } }
  );

  if (!res.ok) {
    console.warn(`fetchLinkedDocs: Jira API error for ${key}: ${res.status}`);
    return [];
  }

  const links = await res.json();

  return links
    .filter((l) => l.object?.title?.startsWith('[AutoDoc]'))
    .map((l) => ({
      id: l.id,
      title: l.object.title.replace('[AutoDoc] ', ''),
      url: l.object.url,
    }));
});

// ─── Resolver: fetch pending docs for a Jira issue ───────────────────────────

resolver.define('fetchPendingDocs', async (req) => {
  const issueKey = req.context.extension.issue.key;
  const slugs = (await storage.get(`pending-index:${issueKey}`)) || [];
  const records = await Promise.all(
    slugs.map((slug) => storage.get(`pending:${issueKey}:${slug}`))
  );
  return records.filter(Boolean);
});

// ─── Resolver: approve a pending doc ─────────────────────────────────────────

resolver.define('approvePendingDoc', async (req) => {
  const issueKey = req.context.extension.issue.key;
  const { slug } = req.payload;

  const record = await storage.get(`pending:${issueKey}:${slug}`);
  if (!record) {
    return { success: false, error: 'Pending doc not found' };
  }

  try {
    // Look up Confluence space
    const spaceRes = await api.asApp().requestConfluence(
      route`/wiki/api/v2/spaces?keys=${record.confluenceSpaceKey}`,
      { headers: { Accept: 'application/json' } }
    );
    const spaceData = await spaceRes.json();
    if (!spaceData.results?.length) {
      throw new Error(`Confluence space '${record.confluenceSpaceKey}' not found`);
    }
    const spaceId = spaceData.results[0].id;
    const baseUrl = new URL(spaceRes.url).origin;

    // Ensure page hierarchy
    const hierarchy = await ensurePageHierarchy(spaceId, record.repoName || 'Repository', baseUrl);

    // Create or update the unit page under its kind subpage
    const parentId = hierarchy.kindPageIds[record.unitKind] ?? hierarchy.kindPageIds['module'];
    const page = await createOrUpdateConfluencePage({
      spaceKey: record.confluenceSpaceKey,
      title: record.title,
      content: record.markdown,
      parentPageId: parentId,
    });

    // Link to Jira issue
    await linkPageToJiraIssue(issueKey, record.title, page.url, page.id);

    // Remove from KVS
    await storage.delete(`pending:${issueKey}:${slug}`);
    await _removeFromIndex(issueKey, slug);

    return { success: true, confluencePageId: page.id, confluencePageUrl: page.url };
  } catch (err) {
    console.error('approvePendingDoc error:', err);
    return { success: false, error: err.message };
  }
});

// ─── Resolver: reject a pending doc ──────────────────────────────────────────

resolver.define('rejectPendingDoc', async (req) => {
  const issueKey = req.context.extension.issue.key;
  const { slug } = req.payload;

  await storage.delete(`pending:${issueKey}:${slug}`);
  await _removeFromIndex(issueKey, slug);

  return { success: true };
});

export const handler = resolver.getDefinitions();

// ─── Signature verification ───────────────────────────────────────────────────

function verifySignature(rawBody, headers) {
  const secret = process.env.WEBHOOK_SECRET;
  if (!secret) {
    // Hard fail — operator must configure the secret before the app accepts requests
    return { valid: false, status: 500, error: 'Webhook secret not configured on server' };
  }

  // Forge webtrigger headers arrive as { 'header-name': ['value'] } arrays
  const sigHeader = (headers['x-autodoc-signature'] ?? [])[0];
  if (!sigHeader) {
    return { valid: false, status: 401, error: 'Missing X-AutoDoc-Signature header' };
  }

  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(rawBody)
    .digest('hex');

  // Constant-time comparison to prevent timing attacks
  const expectedBuf = Buffer.from(expected, 'utf8');
  const actualBuf   = Buffer.from(sigHeader, 'utf8');
  const safe = expectedBuf.length === actualBuf.length &&
    crypto.timingSafeEqual(expectedBuf, actualBuf);

  return safe
    ? { valid: true }
    : { valid: false, status: 401, error: 'Invalid signature' };
}

// ─── Webtrigger: called by GitHub pipeline ────────────────────────────────────

export const webhookHandler = async (event) => {
  // ── Authentication ────────────────────────────────────────────────────────
  const verification = verifySignature(event.body, event.headers ?? {});
  if (!verification.valid) {
    return respond(verification.status, { error: verification.error });
  }

  // ── Parse body ────────────────────────────────────────────────────────────
  let payload;
  try {
    payload = JSON.parse(event.body);
  } catch {
    return respond(400, { error: 'Invalid JSON body' });
  }

  // ── New batch format ──────────────────────────────────────────────────────
  if (payload.units) {
    const { jiraKey, confluenceSpaceKey, repoName, units, repoDoc, prNumber, prTitle } = payload;

    if (!jiraKey || !confluenceSpaceKey || !units) {
      return respond(400, { error: 'Missing required fields: jiraKey, confluenceSpaceKey, units' });
    }

    try {
      const submittedAt = new Date().toISOString();
      let count = 0;

      for (const unit of units) {
        const record = {
          issueKey: jiraKey,
          slug: unit.slug,
          title: unit.title || unit.slug,
          markdown: unit.markdown,
          unitKind: unit.kind || 'module',
          confluenceSpaceKey,
          repoName: repoName || 'Repository',
          submittedAt,
          prNumber,
          prTitle,
        };
        await storage.set(`pending:${jiraKey}:${unit.slug}`, record);
        await _addToIndex(jiraKey, unit.slug);
        count++;
      }

      // Optionally store repo doc separately (not as a pending unit)
      if (repoDoc) {
        await storage.set(`repo-doc:${jiraKey}`, { markdown: repoDoc, submittedAt });
      }

      return respond(200, { success: true, pendingCount: count });
    } catch (err) {
      console.error('webhookHandler batch error:', err);
      return respond(500, { error: err.message });
    }
  }

  // ── Legacy single-doc format (backward compat) ────────────────────────────
  const { jiraKey, docTitle, docContent, confluenceSpaceKey, parentPageId } = payload;

  if (!jiraKey || !docTitle || !docContent || !confluenceSpaceKey) {
    return respond(400, {
      error: 'Missing required fields: jiraKey, docTitle, docContent, confluenceSpaceKey',
    });
  }

  try {
    const page = await createOrUpdateConfluencePage({
      spaceKey: confluenceSpaceKey,
      title: docTitle,
      content: docContent,
      parentPageId,
    });
    await linkPageToJiraIssue(jiraKey, docTitle, page.url, page.id);
    return respond(200, { success: true, confluencePageId: page.id, confluencePageUrl: page.url, jiraIssue: jiraKey });
  } catch (err) {
    console.error('webhookHandler error:', err);
    return respond(500, { error: err.message });
  }
};

// ─── Confluence hierarchy ─────────────────────────────────────────────────────

async function ensurePageHierarchy(spaceId, repoName, baseUrl) {
  const repoPageId = await findOrCreatePage(
    spaceId,
    `[AutoDoc] ${repoName}`,
    null,
    '<p>Auto-generated documentation root for this repository.</p>',
    baseUrl
  );

  const kindPageIds = {};
  for (const [kind, kindTitle] of Object.entries(KIND_PAGE_TITLES)) {
    kindPageIds[kind] = await findOrCreatePage(
      spaceId,
      kindTitle,
      repoPageId,
      `<p>Auto-generated ${kindTitle} documentation.</p>`,
      baseUrl
    );
  }

  return { repoPageId, kindPageIds };
}

async function findOrCreatePage(spaceId, title, parentId, body, baseUrl) {
  // Search for existing page by title in the space
  let existing = null;

  if (parentId) {
    // Search under the parent's children
    const childRes = await api.asApp().requestConfluence(
      route`/wiki/api/v2/pages/${parentId}/children?limit=50`,
      { headers: { Accept: 'application/json' } }
    );
    const childData = await childRes.json();
    existing = childData.results?.find((p) => p.title === title) || null;
  } else {
    // Search by title in space
    const searchRes = await api.asApp().requestConfluence(
      route`/wiki/api/v2/pages?spaceId=${spaceId}&title=${encodeURIComponent(title)}&status=current`,
      { headers: { Accept: 'application/json' } }
    );
    const searchData = await searchRes.json();
    existing = searchData.results?.[0] || null;
  }

  if (existing) {
    return existing.id;
  }

  // Create new page
  const createBody = {
    spaceId,
    status: 'current',
    title,
    body: { representation: 'storage', value: body },
  };
  if (parentId) createBody.parentId = parentId;

  const createRes = await api.asApp().requestConfluence(route`/wiki/api/v2/pages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(createBody),
  });
  const pageData = await createRes.json();

  if (!pageData.id) {
    throw new Error(`Failed to create Confluence page '${title}': ${JSON.stringify(pageData)}`);
  }

  return pageData.id;
}

// ─── Confluence helpers (v2 API) ──────────────────────────────────────────────

async function createOrUpdateConfluencePage({ spaceKey, title, content, parentPageId }) {
  const storageContent = markdownToConfluenceStorage(content);

  const spaceRes = await api.asApp().requestConfluence(
    route`/wiki/api/v2/spaces?keys=${spaceKey}`,
    { headers: { Accept: 'application/json' } }
  );
  const spaceData = await spaceRes.json();
  if (!spaceData.results?.length) {
    throw new Error(`Confluence space '${spaceKey}' not found. Check your confluenceSpaceKey.`);
  }
  const space = spaceData.results[0];
  const spaceId = space.id;

  const baseUrl = new URL(spaceRes.url).origin;

  const searchRes = await api.asApp().requestConfluence(
    route`/wiki/api/v2/pages?spaceId=${spaceId}&title=${encodeURIComponent(title)}&status=current`,
    { headers: { Accept: 'application/json' } }
  );
  const searchData = await searchRes.json();

  let pageData;

  if (searchData.results?.length > 0) {
    const existing = searchData.results[0];
    const updateRes = await api.asApp().requestConfluence(
      route`/wiki/api/v2/pages/${existing.id}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          id: existing.id,
          status: 'current',
          title,
          version: { number: existing.version.number + 1 },
          body: { representation: 'storage', value: storageContent },
        }),
      }
    );
    pageData = await updateRes.json();
  } else {
    const createBody = {
      spaceId,
      status: 'current',
      title,
      body: { representation: 'storage', value: storageContent },
    };
    if (parentPageId) createBody.parentId = parentPageId;

    const createRes = await api.asApp().requestConfluence(route`/wiki/api/v2/pages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(createBody),
    });
    pageData = await createRes.json();
  }

  if (!pageData.id) {
    throw new Error(`Confluence page operation failed: ${JSON.stringify(pageData)}`);
  }

  return { id: pageData.id, url: `${baseUrl}/wiki${pageData._links.webui}` };
}

// ─── Jira helpers ─────────────────────────────────────────────────────────────

async function linkPageToJiraIssue(issueKey, docTitle, pageUrl, pageId) {
  const linkTitle = `[AutoDoc] ${docTitle}`;
  const globalId = `confluence-autodoc-${pageId}`;

  const existingRes = await api.asApp().requestJira(
    route`/rest/api/3/issue/${issueKey}/remotelink`,
    { headers: { Accept: 'application/json' } }
  );
  const existingLinks = await existingRes.json();
  const existingLink = existingLinks.find((l) => l.globalId === globalId);

  const linkBody = {
    globalId,
    application: { type: 'com.atlassian.confluence', name: 'Confluence' },
    relationship: 'Documentation',
    object: {
      url: pageUrl,
      title: linkTitle,
      icon: {
        url16x16: 'https://confluence.atlassian.com/favicon.ico',
        title: 'Confluence Page',
      },
    },
  };

  if (existingLink) {
    await api.asApp().requestJira(
      route`/rest/api/3/issue/${issueKey}/remotelink/${existingLink.id}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(linkBody),
      }
    );
  } else {
    await api.asApp().requestJira(route`/rest/api/3/issue/${issueKey}/remotelink`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(linkBody),
    });
  }
}

// ─── KVS index helpers ────────────────────────────────────────────────────────

async function _addToIndex(issueKey, slug) {
  const current = (await storage.get(`pending-index:${issueKey}`)) || [];
  if (!current.includes(slug)) {
    await storage.set(`pending-index:${issueKey}`, [...current, slug]);
  }
}

async function _removeFromIndex(issueKey, slug) {
  const current = (await storage.get(`pending-index:${issueKey}`)) || [];
  await storage.set(`pending-index:${issueKey}`, current.filter((s) => s !== slug));
}

// ─── Markdown → Confluence Storage Format conversion ─────────────────────────

function markdownToConfluenceStorage(markdown) {
  const lines = markdown.split('\n');
  const output = [];
  let i = 0;
  let inList = null;
  let listItems = [];

  const flushList = () => {
    if (!inList) return;
    output.push(`<${inList}>`);
    listItems.forEach((item) => output.push(`<li>${item}</li>`));
    output.push(`</${inList}>`);
    listItems = [];
    inList = null;
  };

  while (i < lines.length) {
    let line = lines[i];

    const fenceMatch = line.match(/^```(\w*)$/);
    if (fenceMatch) {
      flushList();
      const lang = fenceMatch[1] || 'none';
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      const code = escapeXml(codeLines.join('\n'));
      output.push(
        `<ac:structured-macro ac:name="code">` +
          `<ac:parameter ac:name="language">${lang}</ac:parameter>` +
          `<ac:plain-text-body><![CDATA[${code}]]></ac:plain-text-body>` +
          `</ac:structured-macro>`
      );
      i++;
      continue;
    }

    const h3 = line.match(/^### (.+)$/);
    if (h3) { flushList(); output.push(`<h3>${inlineFormat(h3[1])}</h3>`); i++; continue; }
    const h2 = line.match(/^## (.+)$/);
    if (h2) { flushList(); output.push(`<h2>${inlineFormat(h2[1])}</h2>`); i++; continue; }
    const h1 = line.match(/^# (.+)$/);
    if (h1) { flushList(); output.push(`<h1>${inlineFormat(h1[1])}</h1>`); i++; continue; }

    const ulMatch = line.match(/^[*\-] (.+)$/);
    if (ulMatch) {
      if (inList === 'ol') flushList();
      inList = 'ul';
      listItems.push(inlineFormat(ulMatch[1]));
      i++;
      continue;
    }

    const olMatch = line.match(/^\d+\. (.+)$/);
    if (olMatch) {
      if (inList === 'ul') flushList();
      inList = 'ol';
      listItems.push(inlineFormat(olMatch[1]));
      i++;
      continue;
    }

    if (line.trim() === '') {
      flushList();
      i++;
      continue;
    }

    flushList();
    output.push(`<p>${inlineFormat(line)}</p>`);
    i++;
  }

  flushList();
  return output.join('\n');
}

function inlineFormat(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

function escapeXml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ─── Response helper ──────────────────────────────────────────────────────────

function respond(statusCode, body) {
  return {
    statusCode,
    headers: { 'Content-Type': ['application/json'] },
    body: JSON.stringify(body),
  };
}
