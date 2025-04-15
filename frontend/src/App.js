import React, { useState } from 'react';
import EditAddItem from './components/EditAddItem';
import ManageInventory from './components/ManageInventory';
import ManageAisles from './components/ManageAisles';
import ManageStores from './components/ManageStores';

function App() {
  const [screen, setScreen] = useState('inventory');
  const [editItemData, setEditItemData] = useState(null);
  const [refreshInventoryFlag, setRefreshInventoryFlag] = useState(false);

  // This will force ManageInventory to reload when toggled
  const handleAfterSave = () => {
    setScreen('inventory');
    setRefreshInventoryFlag(f => !f);
  };

  let ScreenComponent;
  if (screen === 'inventory') ScreenComponent = <ManageInventory key={refreshInventoryFlag} onEditItem={item => { setEditItemData(item); setScreen('edit'); }} />;
  else if (screen === 'edit') ScreenComponent = <EditAddItem item={editItemData} afterSave={handleAfterSave} />;
  else if (screen === 'stores') ScreenComponent = <ManageStores />;
  else if (screen === 'aisles') ScreenComponent = <ManageAisles />;

  return (
    <div style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Home Inventory App</h1>
      <nav style={{ marginBottom: 16 }}>
        <button onClick={() => { setScreen('inventory'); setEditItemData(null); }}>Manage Inventory</button>
        <button onClick={() => { setScreen('edit'); setEditItemData(null); }}>Edit/Add Item</button>
        <button onClick={() => setScreen('stores')}>Manage Stores</button>
        <button onClick={() => setScreen('aisles')}>Manage Aisles</button>
      </nav>
      {ScreenComponent}
    </div>
  );
}

export default App;
