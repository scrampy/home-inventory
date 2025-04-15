// TODO: Wire up to backend for full CRUD
// - Fetch items from backend
// - Save new/edited item to backend
// - Delete item from backend

import React, { useState, useEffect } from 'react';

const allStores = ['Walmart', 'Costco', 'Target'];

function EditAddItem({ afterSave }) {
  // UI state
  const [name, setName] = useState('');
  const [aisleId, setAisleId] = useState('');
  const [newAisle, setNewAisle] = useState('');
  const [notes, setNotes] = useState('');
  const [photo, setPhoto] = useState('https://via.placeholder.com/48x48?text=Item');
  const [newStore, setNewStore] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [allLocations, setAllLocations] = useState([]);
  const [locationEntries, setLocationEntries] = useState([]); // [{id, name, quantity}]
  const [newLocationName, setNewLocationName] = useState('');
  const [newLocationQty, setNewLocationQty] = useState(1);
  const [aisleList, setAisleList] = useState([]);
  const [locationEntryError, setLocationEntryError] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch('/api/items').then(r => r.json()),
      fetch('/api/aisles').then(r => r.json()),
      fetch('/api/locations').then(r => r.json())
    ])
      .then(([itemData, aisleData, locationData]) => {
        setItems(itemData);
        setAisleList(aisleData);
        setAllLocations(locationData);
        setLoading(false);
      })
      .catch(() => {
        setError('Failed to load items, aisles, or locations');
        setLoading(false);
      });
  }, []);

  const resetForm = () => {
    setName('');
    setAisleId('');
    setNewAisle('');
    setNotes('');
    setPhoto('https://via.placeholder.com/48x48?text=Item');
    setNewStore('');
    setEditingId(null);
    setLocationEntries([]);
    setNewLocationName('');
    setNewLocationQty(1);
  };

  const handleEdit = item => {
    setEditingId(item.id);
    setName(item.name || '');
    setAisleId(item.aisle_id || '');
    setNotes(item.notes || '');
    setPhoto(item.photo_url || 'https://via.placeholder.com/48x48?text=Item');
    // Convert item.locations to [{id, name, quantity}]
    if (item.locations && Array.isArray(item.locations)) {
      setLocationEntries(item.locations.map(l => ({ id: l.id, name: l.name, quantity: l.quantity || 1 })));
    } else {
      setLocationEntries([]);
    }
  };

  const handleDelete = id => {
    if (!window.confirm('Delete this item?')) return;
    fetch(`/api/items/${id}`, { method: 'DELETE' })
      .then(() => setItems(items => items.filter(i => i.id !== id)));
    if (editingId === id) resetForm();
  };

  const handleSubmit = e => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Name is required');
      return;
    }
    const payload = {
      name,
      notes,
      photo_url: photo,
      locations: locationEntries.map(loc => ({ id: loc.id, name: loc.name, quantity: loc.quantity }))
    };
    if (aisleId) payload.aisle_id = Number(aisleId);
    if (editingId) {
      fetch(`/api/items/${editingId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(r => r.ok ? r.json() : r.text().then(msg => { throw new Error(msg); }))
        .then(updated => {
          setItems(items => items.map(i => i.id === editingId ? updated : i));
          resetForm();
          if (afterSave) afterSave();
        })
        .catch(err => setError('Failed to update item: ' + err.message));
    } else {
      fetch('/api/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(r => r.ok ? r.json() : r.text().then(msg => { throw new Error(msg); }))
        .then(newItem => {
          setItems(items => [...items, newItem]);
          resetForm();
          if (afterSave) afterSave();
        })
        .catch(err => setError('Failed to add item: ' + err.message));
    }
  };

  const addLocationEntry = () => {
    const name = newLocationName.trim();
    const quantity = Number(newLocationQty) || 1;
    if (!name) {
      setLocationEntryError('Location name required');
      return;
    }
    if (locationEntries.some(loc => loc.name.toLowerCase() === name.toLowerCase())) {
      setLocationEntryError('Location already added');
      return;
    }
    const existing = allLocations.find(l => l.name.toLowerCase() === name.toLowerCase());
    setLocationEntries([
      ...locationEntries,
      { id: existing ? existing.id : undefined, name, quantity }
    ]);
    setNewLocationName('');
    setNewLocationQty(1);
    setLocationEntryError('');
  };

  const handleLocationInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addLocationEntry();
    }
  };

  const removeLocationEntry = (name) => {
    setLocationEntries(locationEntries.filter(loc => loc.name !== name));
  };

  const updateLocationQty = (name, qty) => {
    setLocationEntries(locationEntries.map(loc => loc.name === name ? { ...loc, quantity: qty } : loc));
  };

  const handlePhotoChange = e => {
    if (e.target.files && e.target.files[0]) {
      setPhoto(URL.createObjectURL(e.target.files[0]));
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Home">🏠</button>
        <span style={{ fontWeight: 600, fontSize: '1.15em' }}>{editingId ? 'Edit Item' : 'Add Item'}</span>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Shopping">🛒</button>
      </div>
      {error && <div style={{ color: 'red', marginBottom: 14 }}>{error}</div>}
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 18 }}>
          <label htmlFor="item-name" style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Item Name</label>
          <input type="text" id="item-name" value={name} onChange={e => setName(e.target.value)} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4, fontSize: '1em' }} />
        </div>
        <div style={{ marginBottom: 18 }}>
          <label htmlFor="aisle-select" style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Aisle</label>
          <select id="aisle-select" value={aisleId} onChange={e => setAisleId(e.target.value)} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4, fontSize: '1em' }}>
            <option value="">Select Aisle</option>
            {aisleList.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div style={{ marginBottom: 18 }}>
          <label htmlFor="notes" style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Notes</label>
          <textarea id="notes" rows={2} value={notes} onChange={e => setNotes(e.target.value)} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4, fontSize: '1em' }} />
        </div>
        <div style={{ marginBottom: 18 }}>
          <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Photo</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <img src={photo} alt={name} style={{ width: 48, height: 48, borderRadius: 6, objectFit: 'cover', background: '#eee' }} />
            <input type="file" accept="image/*" style={{ display: 'none' }} id="photo-upload" onChange={handlePhotoChange} />
            <label htmlFor="photo-upload" style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', cursor: 'pointer', fontSize: '0.95em' }}>Upload / Change Photo</label>
          </div>
        </div>
        <div style={{ marginBottom: 18 }}>
          <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Locations & Quantities</label>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <select
              value={newLocationName}
              onChange={e => setNewLocationName(e.target.value)}
              style={{ flex: 2, padding: 8, border: '1px solid #ccc', borderRadius: 4 }}
            >
              <option value="">Select location</option>
              {allLocations.map(loc => (
                <option key={loc.id} value={loc.name}>{loc.name}</option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              value={newLocationQty}
              onChange={e => setNewLocationQty(e.target.value)}
              style={{ width: 60, padding: 8, border: '1px solid #ccc', borderRadius: 4 }}
              placeholder="Qty"
            />
            <button type="button" style={{ padding: '8px 16px', background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }} onClick={addLocationEntry}>Add</button>
          </div>
          {locationEntryError && <div style={{ color: 'red', marginBottom: 8 }}>{locationEntryError}</div>}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {locationEntries.map(loc => (
              <span key={loc.name} style={{ display: 'flex', alignItems: 'center', background: '#e3f2fd', borderRadius: 16, padding: '4px 10px', fontSize: '0.98em', marginBottom: 4 }}>
                <span style={{ marginRight: 8 }}>{loc.name}</span>
                <input
                  type="number"
                  min="1"
                  value={loc.quantity}
                  onChange={e => updateLocationQty(loc.name, Number(e.target.value) || 1)}
                  style={{ width: 40, marginRight: 6, border: '1px solid #90caf9', borderRadius: 4, padding: '2px 4px', fontSize: '0.97em' }}
                />
                <button type="button" onClick={() => removeLocationEntry(loc.name)} style={{ background: 'none', border: 'none', color: '#1976d2', fontWeight: 700, fontSize: 18, cursor: 'pointer', marginLeft: 2 }}>×</button>
              </span>
            ))}
          </div>
          {/* DEBUG: Show allLocations for troubleshooting */}
          <div style={{ color: '#888', fontSize: '0.92em', marginTop: 8 }}>
            <strong>Available locations:</strong> {allLocations.map(l => l.name).join(', ') || 'none'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          <button className="save-btn" style={{ flex: 2, background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, padding: '10px 0', fontSize: '1em', cursor: 'pointer' }} type="submit">{editingId ? 'Save Changes' : 'Add Item'}</button>
          {editingId && <button className="delete-btn" style={{ flex: 1, background: '#fff', color: '#d32f2f', border: '1px solid #d32f2f', borderRadius: 4, padding: '10px 0', fontSize: '1em', cursor: 'pointer' }} type="button" onClick={() => handleDelete(editingId)}>Delete Item</button>}
        </div>
      </form>
      <hr style={{ margin: '24px 0' }} />
      <div style={{ fontWeight: 500, marginBottom: 8 }}>All Items</div>
      {items.map(item => (
        <div key={item.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '10px 0' }}>
          <span style={{ flex: 2 }}>{item.name}</span>
          <span style={{ flex: 2, color: '#888', fontSize: '0.97em' }}>{item.aisle_id || 'Unknown'}</span>
          <button onClick={() => handleEdit(item)} style={{ marginLeft: 8, color: '#1976d2', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>✏️</button>
          <button onClick={() => handleDelete(item.id)} style={{ marginLeft: 4, color: '#d32f2f', border: 'none', background: 'none', cursor: 'pointer', fontSize: 18 }}>🗑️</button>
        </div>
      ))}
    </div>
  );
}

export default EditAddItem;
