import React, { useState } from 'react';
import ManageInventory from './components/ManageInventory';
import EditAddItem from './components/EditAddItem';
import ShoppingList from './components/ShoppingList';
import ShoppingListCreation from './components/ShoppingListCreation';
import ManageStores from './components/ManageStores';

function App() {
  const [screen, setScreen] = useState('inventory');
  const [editItemData, setEditItemData] = useState(null);

  let ScreenComponent;
  if (screen === 'inventory') ScreenComponent = <ManageInventory onEditItem={item => { setEditItemData(item); setScreen('edit'); }} />;
  else if (screen === 'edit') ScreenComponent = <EditAddItem item={editItemData} />;
  else if (screen === 'shopping') ScreenComponent = <ShoppingList />;
  else if (screen === 'shopping-create') ScreenComponent = <ShoppingListCreation />;
  else if (screen === 'stores') ScreenComponent = <ManageStores />;

  return (
    <div style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Home Inventory App</h1>
      <nav style={{ marginBottom: 16 }}>
        <button onClick={() => { setScreen('inventory'); setEditItemData(null); }}>Manage Inventory</button>
        <button onClick={() => { setScreen('edit'); setEditItemData(null); }}>Edit/Add Item</button>
        <button onClick={() => setScreen('shopping')}>Shopping List</button>
        <button onClick={() => setScreen('shopping-create')}>Create Shopping List</button>
        <button onClick={() => setScreen('stores')}>Manage Stores</button>
      </nav>
      {ScreenComponent}
    </div>
  );
}

export default App;
