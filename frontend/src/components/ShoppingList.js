import React, { useState } from 'react';

const allStores = ['All Stores', 'Walmart', 'Costco', 'Target'];
const mockList = [
  { id: 1, name: 'Soup', quantity: 5, aisle: 'A3', store: 'Walmart', purchased: true },
  { id: 2, name: 'Coffee', quantity: 2, aisle: 'B1', store: 'Costco', purchased: false },
  { id: 3, name: 'Shampoo', quantity: 1, aisle: 'C7', store: 'Target', purchased: false },
];

function ShoppingList() {
  const [store, setStore] = useState('All Stores');
  const [items, setItems] = useState(mockList);

  const handleCheck = id => {
    setItems(items => items.map(item =>
      item.id === id ? { ...item, purchased: !item.purchased } : item
    ));
  };
  const handleClear = () => {
    setItems(items => items.map(item => item.purchased ? null : item).filter(Boolean));
  };
  const filtered = store === 'All Stores' ? items : items.filter(item => item.store === store);

  return (
    <div style={{ maxWidth: 420, margin: '30px auto', background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px #0001', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Home">🏠</button>
        <span style={{ fontWeight: 600, fontSize: '1.15em' }}>Shopping List</span>
        <button style={{ background: 'none', border: 'none', fontSize: '1.6em', color: '#1976d2', cursor: 'pointer' }} title="Inventory">📦</button>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontWeight: 500, marginRight: 8 }}>Store:</span>
        <select value={store} onChange={e => setStore(e.target.value)} style={{ fontSize: '1em', padding: '6px 10px', borderRadius: 5, border: '1px solid #ccc' }}>
          {allStores.map(s => <option key={s}>{s}</option>)}
        </select>
      </div>
      {filtered.map(item => (
        <div key={item.id} style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #eee', padding: '12px 0' }}>
          <input type="checkbox" checked={item.purchased} onChange={() => handleCheck(item.id)} style={{ marginRight: 12, accentColor: '#1976d2' }} />
          <label style={{ flex: 2, textDecoration: item.purchased ? 'line-through' : undefined, color: item.purchased ? '#bbb' : undefined }}>{item.name}</label>
          <span style={{ width: 36, textAlign: 'right', color: item.purchased ? '#bbb' : '#1976d2', fontWeight: 600, marginRight: 10, textDecoration: item.purchased ? 'line-through' : undefined }}>{item.quantity}</span>
          <span style={{ width: 46, color: '#555', fontSize: '0.97em', fontWeight: 500, marginRight: 10, textAlign: 'center', background: '#e3f2fd', borderRadius: 5 }}>{item.aisle}</span>
          <span style={{ flex: 1, color: '#888', fontSize: '0.95em' }}>{item.store}</span>
        </div>
      ))}
      <button style={{ marginTop: 18, width: '100%', padding: 12, background: '#fff', color: '#d32f2f', border: '1px solid #d32f2f', borderRadius: 4, fontSize: '1.05em', cursor: 'pointer' }} onClick={handleClear}>Clear Purchased Items</button>
    </div>
  );
}

export default ShoppingList;
