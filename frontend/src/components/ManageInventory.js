import React, { useState, useEffect } from 'react';

function ManageInventory({ onEditItem }) {
  const [inventory, setInventory] = useState([]);
  const [items, setItems] = useState([]);
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch('/api/inventory').then(r => r.json()),
      fetch('/api/items').then(r => r.json()),
      fetch('/api/locations').then(r => r.json())
    ])
      .then(([invData, itemData, locData]) => {
        setInventory(invData);
        setItems(itemData);
        setLocations(locData);
        setSelectedLocation(locData.length ? locData[0].name : '');
        setLoading(false);
      })
      .catch(() => {
        setError('Failed to load inventory, items, or locations');
        setLoading(false);
      });
  }, []);

  const handleQtyChange = (id, delta) => {
    const record = inventory.find(r => r.id === id);
    if (!record) return;
    const newQty = Math.max(0, record.quantity + delta);
    fetch(`/api/inventory/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quantity: newQty })
    })
      .then(r => r.json())
      .then(updated => {
        setInventory(inv => inv.map(r => r.id === id ? { ...r, quantity: updated.quantity } : r));
      });
  };

  const handleQtyInput = (id, value) => {
    const qty = Math.max(0, parseInt(value) || 0);
    fetch(`/api/inventory/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quantity: qty })
    })
      .then(r => r.json())
      .then(updated => {
        setInventory(inv => inv.map(r => r.id === id ? { ...r, quantity: updated.quantity } : r));
      });
  };

  // Filter inventory by selected location
  const filteredInventory = selectedLocation
    ? inventory.filter(r => {
        const loc = locations.find(l => l.id === r.location_id);
        return loc && loc.name === selectedLocation;
      })
    : inventory;

  if (loading) return <div>Loading...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Home">🏠</button>
        <div>
          <label htmlFor="location-select" style={{ fontWeight: 500 }}>Location:</label>
          <select
            id="location-select"
            value={selectedLocation}
            onChange={e => setSelectedLocation(e.target.value)}
            style={{ fontSize: '1em', padding: '6px 10px', borderRadius: 5, border: '1px solid #ccc', marginLeft: 8 }}
          >
            {locations.map(loc => <option key={loc.id} value={loc.name}>{loc.name}</option>)}
          </select>
        </div>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Shopping">🛒</button>
      </div>
      {filteredInventory.map(record => {
        const item = items.find(i => i.id === record.item_id);
        return (
          <div key={record.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '12px 0' }}>
            <span style={{ flex: 2 }}>{item?.name || 'Unknown'}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <button style={{ background: '#eee', border: 'none', borderRadius: 4, width: 28, height: 28, fontSize: 18, cursor: 'pointer' }} onClick={() => handleQtyChange(record.id, -1)}>-</button>
              <input
                style={{ width: 40, textAlign: 'center' }}
                type="number"
                value={record.quantity}
                min="0"
                onChange={e => handleQtyInput(record.id, e.target.value)}
              />
              <button style={{ background: '#eee', border: 'none', borderRadius: 4, width: 28, height: 28, fontSize: 18, cursor: 'pointer' }} onClick={() => handleQtyChange(record.id, 1)}>+</button>
            </div>
            <span style={{ flex: 1, color: '#888', fontSize: '0.95em' }}>{item?.store || ''}</span>
          </div>
        );
      })}
      <button 
        style={{ marginTop: 18, width: '100%', padding: 10, background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, fontSize: '1em', cursor: 'pointer' }}
        onClick={() => onEditItem ? onEditItem(null) : null}
      >
        + Add New Item
      </button>
    </div>
  );
}

export default ManageInventory;
