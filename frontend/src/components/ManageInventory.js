import React, { useState, useEffect } from 'react';

function ManageInventory({ onEditItem }) {
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newLocation, setNewLocation] = useState('');
  const [error, setError] = useState('');

  // Fetch locations and items from backend
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch('/api/locations').then(r => r.json()),
      fetch('/api/items').then(r => r.json())
    ]).then(([locs, its]) => {
      setLocations(locs);
      setItems(its);
      setSelectedLocation(locs.length ? locs[0].name : '');
      setLoading(false);
    }).catch(() => {
      setError('Failed to load data from server');
      setLoading(false);
    });
  }, []);

  // Add new location
  const handleAddLocation = () => {
    if (!newLocation.trim()) return;
    fetch('/api/locations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newLocation.trim() })
    })
      .then(r => r.json())
      .then(loc => {
        setLocations(locs => [...locs, loc]);
        setNewLocation('');
      });
  };

  // Change item quantity
  const handleQtyChange = (id, delta) => {
    const item = items.find(i => i.id === id);
    if (!item) return;
    const newQty = Math.max(0, item.quantity + delta);
    fetch(`/api/items/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quantity: newQty })
    })
      .then(r => r.json())
      .then(updated => {
        setItems(items => items.map(i => i.id === id ? updated : i));
      });
  };

  // Direct quantity input
  const handleQtyInput = (id, value) => {
    const qty = Math.max(0, parseInt(value) || 0);
    fetch(`/api/items/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quantity: qty })
    })
      .then(r => r.json())
      .then(updated => {
        setItems(items => items.map(i => i.id === id ? updated : i));
      });
  };

  // Filter items by location
  const filteredItems = selectedLocation
    ? items.filter(item => item.location === selectedLocation)
    : items;

  if (loading) return <div>Loading...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <span style={{ fontWeight: 600, fontSize: '1.15em' }}>Manage Inventory</span>
        <div>
          <label htmlFor="location-select" style={{ fontWeight: 500 }}>Location:</label>
          <select id="location-select" value={selectedLocation} onChange={e => setSelectedLocation(e.target.value)} style={{ fontSize: '1em', padding: '6px 10px', borderRadius: 5, border: '1px solid #ccc', marginLeft: 8 }}>
            {locations.map(loc => <option key={loc.id} value={loc.name}>{loc.name}</option>)}
          </select>
        </div>
        <span></span>
      </div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
        <input
          value={newLocation}
          onChange={e => setNewLocation(e.target.value)}
          placeholder="Add Location"
          style={{ flex: 1, padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }}
        />
        <button type="button" style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', cursor: 'pointer', fontSize: '0.95em' }} onClick={handleAddLocation}>+ Add Location</button>
      </div>
      {filteredItems.map(item => (
        <div key={item.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '12px 0' }}>
          <span style={{ flex: 2 }}>{item.name}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button style={{ background: '#eee', border: 'none', borderRadius: 4, width: 28, height: 28, fontSize: 18, cursor: 'pointer' }} onClick={() => handleQtyChange(item.id, -1)}>-</button>
            <input style={{ width: 40, textAlign: 'center' }} type="number" value={item.quantity} min="0" onChange={e => handleQtyInput(item.id, e.target.value)} />
            <button style={{ background: '#eee', border: 'none', borderRadius: 4, width: 28, height: 28, fontSize: 18, cursor: 'pointer' }} onClick={() => handleQtyChange(item.id, 1)}>+</button>
          </div>
          <span style={{ flex: 1, color: '#888', fontSize: '0.95em' }}>{item.store}</span>
          <button
            style={{ background: 'none', border: 'none', marginLeft: 8, cursor: 'pointer', fontSize: 20, color: '#1976d2' }}
            title="Edit Item"
            onClick={() => onEditItem ? onEditItem(item) : undefined}
            aria-label="Edit"
          >
            ✏️
          </button>
        </div>
      ))}
      <button style={{ marginTop: 18, width: '100%', padding: 10, background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, fontSize: '1em', cursor: 'pointer' }}>+ Add New Item</button>
    </div>
  );
}

export default ManageInventory;
