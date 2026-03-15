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
};

function App() {
  const [activeTab, setActiveTab] = useState('live');
  const [docs, setDocs] = useState(null);
  const [pendingDocs, setPendingDocs] = useState(null);
  const [error, setError] = useState(null);
  const [pendingAction, setPendingAction] = useState(null); // slug being actioned

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
      loadPendingDocs();
      loadDocs();
    } catch {
      setError(`Failed to approve doc: ${slug}`);
    } finally {
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
          Live Docs
        </button>
        <button style={tabStyle('pending')} onClick={() => setActiveTab('pending')}>
          Pending Review {pendingCount > 0 ? `(${pendingCount})` : ''}
        </button>
      </div>

      {activeTab === 'live' && (
        <div>
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
              return (
                <div key={doc.slug} style={styles.pendingCard}>
                  <div style={styles.pendingHeader}>
                    <strong>{doc.title}</strong>
                    <span style={styles.kindBadge}>{doc.unitKind}</span>
                  </div>
                  <div style={styles.preview}>
                    {(doc.markdown || '').slice(0, 200)}{doc.markdown && doc.markdown.length > 200 ? '…' : ''}
                  </div>
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
