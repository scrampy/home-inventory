# Home Inventory Web Application Specification

## High-Level Topics

1. **User Roles & Access** 
   - Two roles: Administrator, Member. 
   - The first user to create a family becomes the Family Administrator. 
   - The Family Administrator can invite other members via email. 
   - Invited users join as Members. 
   - Only the Family Administrator can manage (add/remove) family members. 
   - New users can create a new family or join an existing family via invitation. 

2. **Inventory Structure** 
   - Track items, their quantities, and storage locations. 
   - Items can have multiple locations and multiple stores. 
   - Support for multiple purchase sources (stores). 
   - Ability to view total quantities across all locations. 
   - Filter items by store for shopping purposes. 
   - "No location" and "No store" options should be available for easy entry. 
   - Quick add: Only require name, location (default to "No location"), quantity, and store (default to "No store"). 
   - Additional details (notes, photo, aisle) can be added in a separate details/edit screen. 
   - Users can edit and delete items. 
   - Inventory UI: Action buttons (+, -, ×) are now compact, and the Last Updated column is removed for better mobile/portrait usability.

3. **Collaboration & History**
   - No change tracking or undo/restore features will be implemented. (N/A)
   - The application will only show the current state of the inventory. (N/A)

4. **Access & Platform** 
   - Web application, optimized for mobile devices (responsive design). 
   - Supports multiple families (multi-tenancy). 
   - Designed for cloud hosting. 
   - Technology stack is flexible; options will be considered during technical planning. 

---

## Technology Stack

- **Backend:** Flask (Python) 
- **Frontend:** React 
- **Database:** SQLite (suitable for low user count; can migrate to PostgreSQL on Heroku if needed) 
- **Hosting:** Heroku (easy deployment for both Flask and React) 
- **ORM:** SQLAlchemy (for Flask database access) 
- **Authentication:** Flask-Login or Flask-Security (backend), JWT or session cookies for frontend-backend communication 

---

## Entity Model

### User
- `id` (primary key)
- `email` (unique)
- `name`
- `password_hash`

### Family
- `id` (primary key)
- `name`
- `created_at`

### FamilyMembership
- `id` (primary key)
- `user_id` (foreign key to User)
- `family_id` (foreign key to Family)
- `role` (Administrator or Member)
- `invited_by` (foreign key to User, nullable)
- `joined_at`

### Item
- `id` (primary key)
- `name` (unique, case-insensitive)
- `category` (optional)
- `default_unit` (optional; e.g., can, dozen, bottle)
- `aisle` (optional; e.g., A3, B1, etc.)
- `notes` (optional)
- `photo_url` (optional)

### Location
- `id` (primary key)
- `name` (unique, case-insensitive)

### Store
- `id` (primary key)
- `name` (unique, case-insensitive)

### Inventory
- `id` (primary key)
- `item_id` (foreign key to Item)
- `location_id` (foreign key to Location, nullable for "No location")
- `quantity` (number of units at this location)
- `last_updated` (timestamp)

### ItemStore
- `id` (primary key)
- `item_id` (foreign key to Item)
- `store_id` (foreign key to Store, nullable for "No store")

### ShoppingList
- `id` (primary key)
- `family_id` (foreign key to Family)
- `created_by` (foreign key to User)
- `created_at` (timestamp)
- `is_active` (boolean)

### ShoppingListItem
- `id` (primary key)
- `shopping_list_id` (foreign key to ShoppingList)
- `item_id` (foreign key to Item)
- `is_purchased` (boolean)

---

## Backend API Integration To-Do List

### /locations [GET, POST]
- [x] Ensure GET returns all locations as expected (all tests passing as of 2025-04-25)
- [x] Ensure POST creates a new location (all tests passing as of 2025-04-25)
- [x] Add PUT/PATCH/DELETE for updating/deleting locations if needed (all tests passing as of 2025-04-25)

### /stores [GET, POST]
- [x] Ensure GET returns all stores as expected (all tests passing as of 2025-04-25)
- [x] Ensure POST creates a new store (all tests passing as of 2025-04-25)
- [x] Add PUT/PATCH/DELETE for updating/deleting stores if needed (all tests passing as of 2025-04-25)

### /aisles [GET, POST]
- [x] Ensure GET returns all aisles as expected (currently returns with store_id) (all tests passing as of 2025-04-25)
- [x] Ensure POST creates a new aisle (currently requires store_id) (all tests passing as of 2025-04-25)
- [x] Update for global aisles if needed (remove store_id requirement?) (all tests passing as of 2025-04-25)
- [x] Add PUT/PATCH/DELETE for updating/deleting aisles if needed (all tests passing as of 2025-04-25)

### /items [GET, POST]
- [x] Ensure GET returns all items with all required fields (all tests passing as of 2025-04-25)
- [x] Ensure POST creates a new item (all tests passing as of 2025-04-25)
- [x] Add PUT/PATCH/DELETE for updating/deleting items (all tests passing as of 2025-04-25)

### /inventory [GET, POST]
- [x] Ensure GET returns all inventory records (all tests passing as of 2025-04-25)
- [x] Ensure POST creates a new inventory record (all tests passing as of 2025-04-25)
- [x] Add PUT/PATCH/DELETE for updating/deleting inventory records (all tests passing as of 2025-04-25)

### /inventory/<inv_id> [PATCH]
- [x] Ensure PATCH updates inventory quantity (all tests passing as of 2025-04-25)

---

## Task List (In Progress / Next Steps)

- [ ] Scaffold the React frontend in a `frontend/` directory using npm and set up the initial project structure.
- [ ] Implement basic React screens for:
  - [ ] Manage Inventory (showing items, quantities, locations, and stores, with edit icon to access Edit/Add Item)
  - [ ] Edit/Add Item
  - [ ] Manage Locations
  - [ ] Manage Stores
  - [ ] Shopping List (view, add, check-off items)
- [ ] Provide user-friendly, browser-based workflows for adding locations, stores, aisles, and items (mock data for now).
- [ ] Add seed data and/or initial test data for easier local testing.

---

## Notes & Constraints

- Unique constraints on `name` for Item, Store, and Location to prevent duplicates.
- Names should be standardized (case-insensitive, trimmed).
- Support for summing item quantities across all locations.
- Ability to filter and view items by store.
- User management supports family grouping with Administrator and Member roles.
- Family Administrator manages invitations and member roles.
- No change tracking or undo/restore; only current state is shown.
- Web app will be mobile-optimized, cloud-hosted, and support multiple families.
- Technology stack: Flask (Python), React, SQLite (with future PostgreSQL option), Heroku, SQLAlchemy, Flask-Login/Security, JWT/session cookies.
- Shopping list creation allows users to select items to add to a list, and check them off as purchased (striking out but keeping visible).
- "Low inventory" view shows items below a threshold for easy shopping.
- No notifications or reminders implemented at this stage.
- Items can have an aisle property (per store) to help organize shopping lists by store layout.
- Shopping lists can be filtered by store and sorted by aisle to facilitate efficient shopping.
