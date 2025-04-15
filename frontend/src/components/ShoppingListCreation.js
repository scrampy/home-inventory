import React, { useState } from 'react';

const filterOptions = ['All Items', 'By Store', 'Low Inventory'];
const allItems = [
  { id: 1, name: 'Soup', quantity: 5, store: 'Walmart', low: true },
  { id: 2, name: 'Coffee', quantity: 2, store: 'Costco', low: false },
  { id: 3, name: 'Shampoo', quantity: 1, store: 'Target', low: false },
];

function ShoppingListCreation() {
  const [filter, setFilter] = useState('All Items');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState([]);

  const filteredItems = allItems.filter(item => {
    if (filter === 'Low Inventory' && !item.low) return false;
    if (filter === 'By Store') return true; // For demo, show all
    return true;
  }).filter(item => item.name.toLowerCase().includes(search.toLowerCase()));

  const toggleSelect = id => {
    setSelected(sel => sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id]);
  };

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Home">🏠</button>
        <span style={{ fontWeight: 600, fontSize: '1.15em' }}>Create Shopping List</span>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Inventory">📦</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {filterOptions.map(opt => (
          <button key={opt} className={filter === opt ? 'active' : ''} style={{ flex: 1, padding: '7px 0', background: filter === opt ? '#1976d2' : '#eee', color: filter === opt ? '#fff' : '#1976d2', border: 'none', borderRadius: 4, fontSize: '1em', cursor: 'pointer' }} onClick={() => setFilter(opt)}>{opt}</button>
        ))}
      </div>
      <input type="text" placeholder="Search items..." value={search} onChange={e => setSearch(e.target.value)} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4, fontSize: '1em', marginBottom: 16 }} />
      {filteredItems.map(item => (
        <div key={item.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '10px 0' }}>
          <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggleSelect(item.id)} style={{ marginRight: 12, accentColor: '#1976d2' }} />
          <label style={{ flex: 2 }}>{item.name}</label>
          <span style={{ width: 36, textAlign: 'right', color: '#1976d2', fontWeight: 600, marginRight: 10 }}>{item.quantity}</span>
          <span style={{ flex: 1, color: '#888', fontSize: '0.95em' }}>{item.store}</span>
          {item.low && <span style={{ color: '#d32f2f', fontWeight: 500, fontSize: '0.96em', marginLeft: 6 }}>Low</span>}
        </div>
      ))}
      <button style={{ marginTop: 18, width: '100%', padding: 12, background: '#1976d2', color: '#fff', border: 'none', borderRadius: 4, fontSize: '1.05em', cursor: 'pointer' }}>Create Shopping List</button>
    </div>
  );
}

export default ShoppingListCreation;
