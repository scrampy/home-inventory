import React, { useState, useEffect } from 'react';

function ManageStores() {
  const [stores, setStores] = useState([]);
  const [newStore, setNewStore] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  // Fetch stores from backend
  useEffect(() => {
    setLoading(true);
    fetch('/api/stores')
      .then(r => r.json())
      .then(setStores)
      .catch(() => setError('Failed to load stores'))
      .finally(() => setLoading(false));
  }, []);

  // Add new store
  const handleAddStore = () => {
    if (!newStore.trim()) return;
    fetch('/api/stores', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newStore.trim() })
    })
      .then(r => r.json())
      .then(store => {
        setStores(stores => [...stores, store]);
        setNewStore('');
      });
  };

  // Start editing
  const startEdit = (id, name) => {
    setEditingId(id);
    setEditingName(name);
  };

  // Cancel editing
  const cancelEdit = () => {
    setEditingId(null);
    setEditingName('');
  };

  // Save store name
  const handleSaveEdit = id => {
    if (!editingName.trim()) return;
    fetch(`/api/stores/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: editingName.trim() })
    })
      .then(r => r.json())
      .then(updated => {
        setStores(stores => stores.map(s => s.id === id ? updated : s));
        cancelEdit();
      });
  };

  // Delete store
  const handleDelete = id => {
    if (!window.confirm('Delete this store?')) return;
    fetch(`/api/stores/${id}`, { method: 'DELETE' })
      .then(() => setStores(stores => stores.filter(s => s.id !== id)));
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <span style={{ fontWeight: 600, fontSize: '1.15em' }}>Manage Stores</span>
      <div style={{ margin: '18px 0', display: 'flex', gap: 8 }}>
        <input
          value={newStore}
          onChange={e => setNewStore(e.target.value)}
          placeholder="Add Store"
          style={{ flex: 1, padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }}
        />
        <button type="button" style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', cursor: 'pointer', fontSize: '0.95em' }} onClick={handleAddStore}>+ Add Store</button>
      </div>
      {stores.map(store => (
        <div key={store.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '10px 0' }}>
          {editingId === store.id ? (
            <>
              <input
                value={editingName}
                onChange={e => setEditingName(e.target.value)}
                style={{ flex: 2, padding: '4px 10px', borderRadius: 8, border: '1px solid #ccc', fontSize: '0.95em' }}
              />
              <button onClick={() => handleSaveEdit(store.id)} style={{ marginLeft: 8, color: '#1976d2', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>💾</button>
              <button onClick={cancelEdit} style={{ marginLeft: 4, color: '#888', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✖️</button>
            </>
          ) : (
            <>
              <span style={{ flex: 2 }}>{store.name}</span>
              <button onClick={() => startEdit(store.id, store.name)} style={{ marginLeft: 8, color: '#1976d2', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✏️</button>
              <button onClick={() => handleDelete(store.id)} style={{ marginLeft: 4, color: '#d32f2f', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>🗑️</button>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

export default ManageStores;
