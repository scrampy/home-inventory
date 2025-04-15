import React, { useState } from 'react';

const allLocations = ['Pantry', 'Freezer', 'No location'];
const allStores = ['Walmart', 'Costco', 'Target'];

function EditAddItem() {
  const [name, setName] = useState('Soup');
  const [locations, setLocations] = useState(['Pantry', 'Freezer']);
  const [stores, setStores] = useState(['Walmart', 'Costco']);
  const [aisleList, setAisleList] = useState(['A3', 'B1', 'C7']);
  const [aisle, setAisle] = useState('A3');
  const [newAisle, setNewAisle] = useState('');
  const [quantity, setQuantity] = useState(5);
  const [notes, setNotes] = useState('Canned, expires 2026');
  const [photo, setPhoto] = useState('https://via.placeholder.com/48x48?text=Soup');
  const [newLocation, setNewLocation] = useState('');
  const [newStore, setNewStore] = useState('');

  const removeLocation = loc => setLocations(locs => locs.filter(l => l !== loc));
  const addLocation = () => {
    if (newLocation && !locations.includes(newLocation)) {
      setLocations([...locations, newLocation]);
      setNewLocation('');
    }
  };
  const removeStore = s => setStores(sts => sts.filter(st => st !== s));
  const addStore = () => {
    if (newStore && !stores.includes(newStore)) {
      setStores([...stores, newStore]);
      setNewStore('');
    }
  };
  const handlePhotoChange = e => {
    if (e.target.files && e.target.files[0]) {
      setPhoto(URL.createObjectURL(e.target.files[0]));
    }
  };

  // Aisle selection logic
  const handleSelectAisle = aisleName => setAisle(aisleName);
  const handleAddAisle = () => {
    const trimmed = newAisle.trim();
    if (trimmed && !aisleList.includes(trimmed)) {
      setAisleList([...aisleList, trimmed]);
      setAisle(trimmed);
      setNewAisle('');
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Home">🏠</button>
        <span style={{ fontWeight: 600, fontSize: '1.15em' }}>Edit Item</span>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Shopping">🛒</button>
      </div>
      <form onSubmit={e => e.preventDefault()}>
        <div style={{ marginBottom: 18 }}>
          <label htmlFor="item-name" style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Item Name</label>
          <input type="text" id="item-name" value={name} onChange={e => setName(e.target.value)} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4, fontSize: '1em' }} />
        </div>
        <div style={{ marginBottom: 18 }}>
          <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Locations</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
            {locations.map(loc => (
              <span key={loc} style={{ background: '#e3f2fd', color: '#1976d2', borderRadius: 12, padding: '4px 12px', fontSize: '0.97em', display: 'flex', alignItems: 'center' }}>
                {loc}
                <span style={{ marginLeft: 6, cursor: 'pointer', color: '#888' }} onClick={() => removeLocation(loc)}>×</span>
              </span>
            ))}
            <input value={newLocation} onChange={e => setNewLocation(e.target.value)} placeholder="Add Location" style={{ padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }} />
            <button type="button" style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', marginLeft: 4, cursor: 'pointer', fontSize: '0.95em' }} onClick={addLocation}>+ Add Location</button>
          </div>
        </div>
        <div style={{ marginBottom: 18 }}>
          <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Stores</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
            {stores.map(s => (
              <span key={s} style={{ background: '#e3f2fd', color: '#1976d2', borderRadius: 12, padding: '4px 12px', fontSize: '0.97em', display: 'flex', alignItems: 'center' }}>
                {s}
                <span style={{ marginLeft: 6, cursor: 'pointer', color: '#888' }} onClick={() => removeStore(s)}>×</span>
              </span>
            ))}
            <input value={newStore} onChange={e => setNewStore(e.target.value)} placeholder="Add Store" style={{ padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }} />
            <button type="button" style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', marginLeft: 4, cursor: 'pointer', fontSize: '0.95em' }} onClick={addStore}>+ Add Store</button>
          </div>
        </div>
        <div style={{ marginBottom: 18 }}>
          <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Aisle</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
            {aisleList.map(a => (
              <button
                key={a}
                type="button"
                onClick={() => handleSelectAisle(a)}
                style={{
                  background: aisle === a ? '#1976d2' : '#e3f2fd',
                  color: aisle === a ? '#fff' : '#1976d2',
                  border: 'none',
                  borderRadius: 12,
                  padding: '4px 12px',
                  fontSize: '0.97em',
                  cursor: 'pointer',
                  fontWeight: aisle === a ? 600 : 400,
                  boxShadow: aisle === a ? '0 0 0 2px #1976d2' : undefined
                }}
              >
                {a}
              </button>
            ))}
            <input
              value={newAisle}
              onChange={e => setNewAisle(e.target.value)}
              placeholder="Add Aisle"
              style={{ padding: '4px 10px', borderRadius: 12, border: '1px solid #ccc', fontSize: '0.95em' }}
            />
            <button
              type="button"
              style={{ background: '#eee', color: '#1976d2', border: 'none', borderRadius: 12, padding: '4px 10px', marginLeft: 4, cursor: 'pointer', fontSize: '0.95em' }}
              onClick={handleAddAisle}
            >
              + Add Aisle
            </button>
          </div>
        </div>
        <div style={{ marginBottom: 18 }}>
          <label htmlFor="quantity" style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Quantity</label>
          <input type="number" id="quantity" value={quantity} min="0" onChange={e => setQuantity(Math.max(0, parseInt(e.target.value)||0))} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4, fontSize: '1em' }} />
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
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          <button className="save-btn" style={{ flex: 2, background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, padding: '10px 0', fontSize: '1em', cursor: 'pointer' }} type="submit">Save Changes</button>
          <button className="delete-btn" style={{ flex: 1, background: '#fff', color: '#d32f2f', border: '1px solid #d32f2f', borderRadius: 4, padding: '10px 0', fontSize: '1em', cursor: 'pointer' }} type="button">Delete Item</button>
        </div>
      </form>
    </div>
  );
}

export default EditAddItem;
