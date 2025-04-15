import React, { useState, useEffect } from 'react';

function ManageAisles() {
  const [aisles, setAisles] = useState([]);
  const [stores, setStores] = useState([]);
  const [newAisle, setNewAisle] = useState('');
  const [newStoreId, setNewStoreId] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [editingStoreId, setEditingStoreId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch('/api/aisles').then(r => r.json()),
      fetch('/api/stores').then(r => r.json())
    ]).then(([aisleData, storeData]) => {
      setAisles(aisleData);
      setStores(storeData);
      setLoading(false);
    }).catch(() => {
      setError('Failed to load aisles or stores');
      setLoading(false);
    });
  }, []);

  const handleAddAisle = () => {
    if (!newAisle.trim() || !newStoreId) return;
    fetch('/api/aisles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newAisle.trim(), store_id: Number(newStoreId) })
    })
      .then(r => r.json())
      .then(aisle => {
        setAisles(aisles => [...aisles, aisle]);
        setNewAisle('');
        setNewStoreId('');
      });
  };

  const startEdit = (id, name, storeId) => {
    setEditingId(id);
    setEditingName(name);
    setEditingStoreId(storeId);
  };
  const cancelEdit = () => {
    setEditingId(null);
    setEditingName('');
    setEditingStoreId('');
  };
  const handleSaveEdit = id => {
    if (!editingName.trim() || !editingStoreId) return;
    fetch(`/api/aisles/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: editingName.trim(), store_id: Number(editingStoreId) })
    })
      .then(r => r.json())
      .then(updated => {
        setAisles(aisles => aisles.map(a => a.id === id ? updated : a));
        cancelEdit();
      });
  };
  const handleDelete = id => {
    if (!window.confirm('Delete this aisle?')) return;
    fetch(`/api/aisles/${id}`, { method: 'DELETE' })
      .then(() => setAisles(aisles => aisles.filter(a => a.id !== id)));
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;

  return (
    <div style={{ maxWidth: 460, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <span style={{ fontWeight: 600, fontSize: '1.15em' }}>Manage Aisles</span>
      <div style={{ margin: '18px 0', display: 'flex', gap: 8 }}>
        <input
          value={newAisle}
          onChange={e => setNewAisle(e.target.value)}
          placeholder="Aisle Name"
          style={{ flex: 2, padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }}
        />
        <select value={newStoreId} onChange={e => setNewStoreId(e.target.value)} style={{ flex: 2, padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }}>
          <option value="">Select Store</option>
          {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button type="button" style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', cursor: 'pointer', fontSize: '0.95em' }} onClick={handleAddAisle}>+ Add Aisle</button>
      </div>
      {aisles.map(aisle => (
        <div key={aisle.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '10px 0' }}>
          {editingId === aisle.id ? (
            <>
              <input
                value={editingName}
                onChange={e => setEditingName(e.target.value)}
                style={{ flex: 2, padding: '4px 10px', borderRadius: 8, border: '1px solid #ccc', fontSize: '0.95em' }}
              />
              <select value={editingStoreId} onChange={e => setEditingStoreId(e.target.value)} style={{ flex: 2, padding: '4px 10px', borderRadius: 8, border: '1px solid #ccc', fontSize: '0.95em' }}>
                <option value="">Select Store</option>
                {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <button onClick={() => handleSaveEdit(aisle.id)} style={{ marginLeft: 8, color: '#1976d2', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>💾</button>
              <button onClick={cancelEdit} style={{ marginLeft: 4, color: '#888', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✖️</button>
            </>
          ) : (
            <>
              <span style={{ flex: 2 }}>{aisle.name}</span>
              <span style={{ flex: 2, color: '#888', fontSize: '0.97em' }}>{stores.find(s => s.id === aisle.store_id)?.name || 'Unknown'}</span>
              <button onClick={() => startEdit(aisle.id, aisle.name, aisle.store_id)} style={{ marginLeft: 8, color: '#1976d2', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✏️</button>
              <button onClick={() => handleDelete(aisle.id)} style={{ marginLeft: 4, color: '#d32f2f', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>🗑️</button>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

export default ManageAisles;
