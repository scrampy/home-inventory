# Home Inventory App: User Flow Scenarios

This document outlines the key user flows and UI/backend interactions inferred from the codebase. It is intended as a reference for test development and QA, ensuring that all automated and manual tests accurately reflect real user behavior and application requirements.

---

## How to Use This Document
- **Test development (Playwright, etc.) must follow these flows.**
- Automated and manual tests should simulate realistic user behavior, including all required UI steps (e.g., logging in, selecting locations).
- Update this document if the UI or backend flows change.

---

## Key User Flows

### 1. Add Item to Inventory
1. **User logs in** (required for all inventory actions).
2. **User selects a location** from the dropdown on the Inventory screen.
3. **User fills out the "Add / Update Items" form:**
    - Selects an item from the dropdown.
    - Enters quantity.
    - Submits the form.
4. **Inventory table updates** to show the item in the selected location with one row per item, featuring minimal button width for +, -, and delete actions.

### 2. Add Location
1. User logs in.
2. User navigates to the Locations screen.
3. User fills out the "Add Location" form and submits.
4. New location appears in dropdowns throughout the app.

### 3. Add Store
1. User logs in.
2. User navigates to the Stores screen.
3. User fills out the "Add Store" form and submits.
4. Store is available for assignment to items/locations.

### 4. Assign Item to Location
1. User logs in.
2. User navigates to the Inventory screen.
3. User selects a location.
4. User adds/updates an item for that location via the form.
5. Item appears in the table for that location.

### 5. Update Inventory Quantity
1. User logs in and selects a location.
2. User uses the +/- buttons in the inventory table to change quantity.
3. Table updates to reflect the new quantity.

### 6. Remove Item from Inventory
1. User logs in and selects a location.
2. User clicks the delete (X) button for an item in the inventory table.
3. User confirms deletion in the confirmation dialog.
4. Item is removed from the table for that location.

---

## Recent Test Alignment

- As of 2025-04-26, the `test_inventory_table_mobile_responsive` Playwright test was updated to follow these flows:
    - The test now logs in, creates inventory data, and **selects a location in the dropdown before asserting** on inventory table contents and action buttons.
    - This ensures the test accurately matches user behavior and the requirements described above.
- All future UI/E2E tests must similarly adhere to these documented flows.
- Inventory screen now shows one row per item with minimal button width for +, -, and delete actions.
- "Last Update" column removed for a cleaner, less cramped appearance.
- Confirmed via automated UI tests.

---

## General Principles
- **Authentication is required** for all inventory, location, store, and item management actions.
- **Selecting a location is required** to view or modify inventory for that location.
- **All UI forms and actions must be exercised via the frontend** to ensure end-to-end correctness.

---

## Test Development Guidance
- **All automated tests must follow these user flows.**
- Tests must always log in, select a location where required, and interact with the UI as a user would.
- Direct backend/API calls should only be used for setup/teardown, not for simulating user actions in UI tests.
- If any UI or backend flows change, update this document and corresponding tests accordingly.

---

## Scenario To-Do List
- [x] Inventory Management (mobile): Add, update, and delete inventory items; select location; verify responsive table and tap targets. (Tested and passed)
- [x] Locations Management (mobile): Add and remove locations; verify responsive table and tap targets. (Tested and passed)
- [x] Stores Management (mobile): Add and remove stores; verify responsive table and tap targets. (Tested and passed)
- [x] Aisles Management (mobile): Add and remove aisles; verify responsive table and tap targets. (Tested and passed)
- [x] Master Items (mobile): Add, edit, and delete master items; add to shopping list; verify tap targets. (Tested and passed)
- [x] Shopping List (mobile): Add, check off, and remove items; verify responsive table and tap targets. (Tested and passed)

---

_Last updated: 2025-04-26_
