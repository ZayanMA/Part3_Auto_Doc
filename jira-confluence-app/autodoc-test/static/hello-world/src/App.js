import React, { useEffect, useState } from 'react';
import { events, invoke } from '@forge/bridge';

const styles = {
  container: { fontFamily: 'sans-serif', fontSize: '14px', padding: '8px 0' },
  tabBar: { display: 'flex', borderBottom: '2px solid #DFE1E6', marginBottom: '12px' },
  tab: {
    padding: '8px 16px',
    cursor: 'pointer',
    fontWeight: 500,
    color: '#6B778C',
    border: 'none',
    background: 'none',
    borderBottom: '2px solid transparent',
    marginBottom: '-2px',
  },
  activeTab: {
    color: '#0052CC',
    borderBottom: '2px solid #0052CC',
  },
  title: { fontWeight: 600, marginBottom: '8px', color: '#172B4D' },
  link: {
    display: 'block', color: '#0052CC', textDecoration: 'none',
    marginBottom: '6px', padding: '6px 8px', background: '#F4F5F7', borderRadius: '3px',
  },
  empty: { color: '#6B778C', fontStyle: 'italic' },
  error: { color: '#DE350B' },
  loading: { color: '#6B778C' },
  pendingCard: {
    border: '1px solid #DFE1E6', borderRadius: '4px', padding: '10px 12px',
    marginBottom: '10px', background: '#FAFBFC',
  },
  pendingHeader: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' },
  kindBadge: {
    fontSize: '11px', fontWeight: 600, padding: '2px 6px',
    borderRadius: '3px', background: '#EBECF0', color: '#172B4D', textTransform: 'uppercase',
  },
  preview: { fontSize: '12px', color: '#6B778C', marginBottom: '8px', fontFamily: 'monospace' },
  timestamp: { fontSize: '11px', color: '#97A0AF', marginBottom: '8px' },
  buttonRow: { display: 'flex', gap: '8px' },
  approveBtn: {
    padding: '5px 12px', background: '#36B37E', color: '#fff', border: 'none',
    borderRadius: '3px', cursor: 'pointer', fontWeight: 500,
  },
  rejectBtn: {
    padding: '5px 12px', background: '#FF5630', color: '#fff', border: 'none',
    borderRadius: '3px', cursor: 'pointer', fontWeight: 500,
  },
  disabledBtn: { opacity: 0.6, cursor: 'not-allowed' },
  toggleBtn: {
    marginLeft: 'auto', padding: '3px 8px', background: 'none',
    border: '1px solid #DFE1E6', borderRadius: '3px', cursor: 'pointer',
    fontSize: '12px', color: '#6B778C', whiteSpace: 'nowrap',
  },
  previewPanel: {
    maxHeight: '260px', overflowY: 'auto',
    borderTop: '1px solid #DFE1E6', padding: '8px',
    marginBottom: '8px',
  },
  mdH1: { fontSize: '16px', fontWeight: 700, margin: '8px 0 4px', color: '#172B4D' },
  mdH2: { fontSize: '14px', fontWeight: 700, margin: '6px 0 4px', color: '#172B4D' },
  mdH3: { fontSize: '13px', fontWeight: 600, margin: '4px 0 2px', color: '#172B4D' },
  mdCode: {
    background: '#F4F5F7', padding: '1px 4px', borderRadius: '3px',
    fontFamily: 'monospace', fontSize: '12px',
  },
  mdPre: {
    background: '#F4F5F7', padding: '8px', borderRadius: '3px',
    fontFamily: 'monospace', fontSize: '12px', overflowX: 'auto',
    whiteSpace: 'pre-wrap', margin: '4px 0',
  },
  mdUl: { margin: '4px 0', paddingLeft: '18px' },
  mdLi: { margin: '2px 0' },
  mdP: { margin: '4px 0', lineHeight: '1.5' },
  confluenceCallout: {
    background: '#DEEBFF', border: '1px solid #B3D4FF', borderRadius: '3px',
    padding: '6px 10px', marginBottom: '10px', fontSize: '12px', color: '#0747A6',
  },
};

/** Convert inline markdown (bold, italic, inline code) to React elements. */
function renderInline(text, keyPrefix) {
  const parts = [];
  const pattern = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/g;
  let last = 0;
  let match;
  let idx = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    if (match[2] !== undefined) {
      parts.push(<strong key={`${keyPrefix}-b${idx}`}>{match[2]}</strong>);
    } else if (match[3] !== undefined) {
      parts.push(<em key={`${keyPrefix}-i${idx}`}>{match[3]}</em>);
    } else if (match[4] !== undefined) {
      parts.push(<code key={`${keyPrefix}-c${idx}`} style={styles.mdCode}>{match[4]}</code>);
    }
    last = match.index + match[0].length;
    idx++;
  }
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  return parts;
}

/** Minimal markdown → React renderer (no external deps). */
function SimpleMarkdown({ content }) {
  if (!content) return null;

  const elements = [];
  // Split into blocks by double newlines
  const rawBlocks = content.split(/\n\n+/);

  rawBlocks.forEach((block, bi) => {
    const trimmed = block.trim();
    if (!trimmed) return;

    // Fenced code block
    if (trimmed.startsWith('```')) {
      const lines = trimmed.split('\n');
      const codeLines = lines.slice(1, lines[lines.length - 1].trim() === '```' ? lines.length - 1 : lines.length);
      elements.push(
        <pre key={`b${bi}`} style={styles.mdPre}><code>{codeLines.join('\n')}</code></pre>
      );
      return;
    }

    // Heading h1
    if (trimmed.startsWith('# ')) {
      elements.push(<h1 key={`b${bi}`} style={styles.mdH1}>{renderInline(trimmed.slice(2), `b${bi}`)}</h1>);
      return;
    }
    // Heading h2
    if (trimmed.startsWith('## ')) {
      elements.push(<h2 key={`b${bi}`} style={styles.mdH2}>{renderInline(trimmed.slice(3), `b${bi}`)}</h2>);
      return;
    }
    // Heading h3
    if (trimmed.startsWith('### ')) {
      elements.push(<h3 key={`b${bi}`} style={styles.mdH3}>{renderInline(trimmed.slice(4), `b${bi}`)}</h3>);
      return;
    }

    // List block (unordered)
    const lines = trimmed.split('\n');
    const isUl = lines.every(l => /^[-*] /.test(l.trim()) || l.trim() === '');
    if (isUl && lines.some(l => /^[-*] /.test(l.trim()))) {
      elements.push(
        <ul key={`b${bi}`} style={styles.mdUl}>
          {lines.filter(l => /^[-*] /.test(l.trim())).map((l, li) => (
            <li key={li} style={styles.mdLi}>{renderInline(l.trim().slice(2), `b${bi}li${li}`)}</li>
          ))}
        </ul>
      );
      return;
    }

    // Ordered list
    const isOl = lines.every(l => /^\d+\. /.test(l.trim()) || l.trim() === '');
    if (isOl && lines.some(l => /^\d+\. /.test(l.trim()))) {
      elements.push(
        <ol key={`b${bi}`} style={styles.mdUl}>
          {lines.filter(l => /^\d+\. /.test(l.trim())).map((l, li) => (
            <li key={li} style={styles.mdLi}>{renderInline(l.trim().replace(/^\d+\. /, ''), `b${bi}ol${li}`)}</li>
          ))}
        </ol>
      );
      return;
    }

    // Paragraph
    elements.push(
      <p key={`b${bi}`} style={styles.mdP}>{renderInline(trimmed.replace(/\n/g, ' '), `b${bi}`)}</p>
    );
  });

  return <div>{elements}</div>;
}

function getKindStyle(kind) {
  const map = {
    api:     { background: '#EAE4F5', color: '#5E4DB2' },
    models:  { background: '#DEEBFF', color: '#0747A6' },
    config:  { background: '#FFFAE6', color: '#172B4D' },
    cli:     { background: '#E3FCEF', color: '#006644' },
    tests:   { background: '#FFEBE6', color: '#BF2600' },
    module:  { background: '#EBECF0', color: '#172B4D' },
  };
  return map[kind?.toLowerCase()] ?? map.module;
}

function App() {
  const [activeTab, setActiveTab] = useState('live');
  const [docs, setDocs] = useState(null);
  const [pendingDocs, setPendingDocs] = useState(null);
  const [error, setError] = useState(null);
  const [pendingAction, setPendingAction] = useState(null); // slug being actioned
  const [expandedSlug, setExpandedSlug] = useState(null);
  const [justApproved, setJustApproved] = useState(new Set());

  const loadDocs = () => {
    invoke('fetchLinkedDocs')
      .then((data) => { setDocs(data); setError(null); })
      .catch(() => setError('Failed to load linked documentation.'));
  };

  const loadPendingDocs = () => {
    invoke('fetchPendingDocs')
      .then((data) => { setPendingDocs(data); setError(null); })
      .catch(() => setError('Failed to load pending documentation.'));
  };

  useEffect(() => {
    loadDocs();
    loadPendingDocs();
    const sub = events.on('JIRA_ISSUE_CHANGED', () => { loadDocs(); loadPendingDocs(); });
    return () => { sub.then((s) => s.unsubscribe()); };
  }, []);

  const handleApprove = async (slug) => {
    setPendingAction(slug);
    try {
      await invoke('approvePendingDoc', { slug });
      setJustApproved(prev => new Set([...prev, slug]));
      setTimeout(() => {
        setJustApproved(prev => { const next = new Set(prev); next.delete(slug); return next; });
        loadPendingDocs();
        loadDocs();
      }, 700);
    } catch {
      setError(`Failed to approve doc: ${slug}`);
      setPendingAction(null);
    }
  };

  const handleReject = async (slug) => {
    setPendingAction(slug);
    try {
      await invoke('rejectPendingDoc', { slug });
      loadPendingDocs();
    } catch {
      setError(`Failed to reject doc: ${slug}`);
    } finally {
      setPendingAction(null);
    }
  };

  const toggleExpand = (slug) => {
    setExpandedSlug(prev => prev === slug ? null : slug);
  };

  const pendingCount = pendingDocs ? pendingDocs.length : 0;

  const tabStyle = (tab) => ({
    ...styles.tab,
    ...(activeTab === tab ? styles.activeTab : {}),
  });

  return (
    <div style={styles.container}>
      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.tabBar}>
        <button style={tabStyle('live')} onClick={() => setActiveTab('live')}>
          Live Docs · Confluence
        </button>
        <button style={tabStyle('pending')} onClick={() => setActiveTab('pending')}>
          Pending Review {pendingCount > 0 ? `(${pendingCount})` : ''}
        </button>
      </div>

      {activeTab === 'live' && (
        <div>
          <div style={styles.confluenceCallout}>
            Approved docs are published to Confluence automatically
          </div>
          {!docs ? (
            <div style={styles.loading}>Loading documentation…</div>
          ) : docs.length === 0 ? (
            <div style={styles.empty}>No documentation generated yet for this issue.</div>
          ) : (
            docs.map((doc) => (
              <a key={doc.id} href={doc.url} target="_blank" rel="noopener noreferrer" style={styles.link}>
                {doc.title}
              </a>
            ))
          )}
        </div>
      )}

      {activeTab === 'pending' && (
        <div>
          {!pendingDocs ? (
            <div style={styles.loading}>Loading pending docs…</div>
          ) : pendingDocs.length === 0 ? (
            <div style={styles.empty}>No pending documentation to review.</div>
          ) : (
            pendingDocs.map((doc) => {
              const isActioning = pendingAction === doc.slug;
              const isExpanded = expandedSlug === doc.slug;
              const isFlashing = justApproved.has(doc.slug);
              const cardStyle = {
                ...styles.pendingCard,
                ...(isFlashing ? { background: '#E3FCEF', borderColor: '#36B37E' } : {}),
              };
              return (
                <div key={doc.slug} style={cardStyle}>
                  <div style={styles.pendingHeader}>
                    <strong>{doc.title}</strong>
                    <span style={{ ...styles.kindBadge, ...getKindStyle(doc.unitKind) }}>{doc.unitKind}</span>
                    <button style={styles.toggleBtn} onClick={() => toggleExpand(doc.slug)}>
                      {isExpanded ? 'Preview ▲' : 'Preview ▼'}
                    </button>
                  </div>
                  {isExpanded ? (
                    <div style={styles.previewPanel}>
                      <SimpleMarkdown content={doc.markdown} />
                    </div>
                  ) : (
                    <div style={styles.preview}>
                      {(doc.markdown || '').slice(0, 200)}{doc.markdown && doc.markdown.length > 200 ? '…' : ''}
                    </div>
                  )}
                  <div style={styles.timestamp}>
                    Submitted: {doc.submittedAt ? new Date(doc.submittedAt).toLocaleString() : 'unknown'}
                  </div>
                  <div style={styles.buttonRow}>
                    <button
                      style={{ ...styles.approveBtn, ...(isActioning ? styles.disabledBtn : {}) }}
                      disabled={isActioning}
                      onClick={() => handleApprove(doc.slug)}
                    >
                      {isActioning ? 'Working…' : 'Approve'}
                    </button>
                    <button
                      style={{ ...styles.rejectBtn, ...(isActioning ? styles.disabledBtn : {}) }}
                      disabled={isActioning}
                      onClick={() => handleReject(doc.slug)}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

export default App;
