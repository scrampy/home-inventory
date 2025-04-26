# Mobile UI Requirements & Progress Tracker

_Last updated: 2025-04-26_

## **Summary & Goals**
- **Goal:** Ensure the Home Inventory web app UI works optimally on iPhone and Android phones (portrait mode). No tablet/landscape, accessibility, or gesture requirements. No color/style changes required.
- **Scope:** All current UI screens (Flask + Bootstrap 5 templates). No React or native app work. Continue using Playwright for testing.

---

## **Findings (Initial Review)**
- The app uses Flask/Jinja2 templates with Bootstrap 5 for layout/styling.
- No custom CSS or JS detected; all UI is server-rendered HTML.
- Bootstrap 5 provides mobile responsiveness, but only if its grid/classes are used properly.
- The `<meta name="viewport">` tag is missing from `base.html` (needed for mobile scaling).
- The navbar uses `navbar-expand-lg` and inline links, which may not collapse to a hamburger menu on small screens.
- No evidence of desktop-only features or tablet/landscape-specific code.

---

## **Recommendations & Plan**

### **Immediate Actions**
- [x] Add `<meta name="viewport" content="width=device-width, initial-scale=1">` to `<head>` in `base.html`.
- [x] Refactor navbar in `base.html` to use Bootstrap's responsive collapse (hamburger menu) for mobile (**Done**; tested with Playwright, 2025-04-26)

### **Template Audit & Remediation**
- [x] Review all templates for:
    - Use of Bootstrap grid (`container`, `row`, `col-*`) and responsive utilities
    - Fixed-width elements, tables, or forms that may overflow on small screens
    - Tap target size and spacing
    - Horizontal scrolling or overflow issues
- [x] For each template, document mobile issues and propose fixes.

### **Testing**
- [x] Ensure Playwright tests cover mobile viewport sizes (e.g., 375x667 for iPhone, 360x640 for Android).
- [x] Add/update tests to validate navigation and layout at mobile breakpoints.

---

## **To-Do List & Progress Tracker**

### **Meta & Navbar**
- [x] Add viewport meta tag to `base.html` (**Done**; tested with Playwright, 2025-04-26)
- [x] Refactor navbar for mobile collapse (**Done**; tested with Playwright, 2025-04-26)

### **Templates**
- [x] Audit and document each template for mobile responsiveness:
    - [x] `inventory.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap table inside `.table-responsive` wrapper. Table is horizontally scrollable on mobile.
        - Action buttons are visible after selecting a location.
        - No fixed-width columns detected.
        - **Issue:** Table is empty unless a location is selected. This is by design, but should be documented for test clarity.
        - **Proposed Fix:** Add a placeholder row or message (e.g., "Select a location to view inventory") when no location is selected. Ensure all table actions/buttons remain accessible at mobile breakpoints.
      - **Status:** Responsive; minor UX improvement suggested.
      - **Recent Improvements (2025-04-26):** Inventory UI now has much more compact +, -, and delete (×) buttons, reducing horizontal space usage and improving portrait/mobile usability. The "Last Updated" column was removed from the inventory table for a cleaner, less cramped look. All inventory-related UI tests pass after these changes.
    - [x] `locations.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap table (`.table-striped`) and input group for the add-location form.
        - **Issue:** Table is not wrapped in `.table-responsive`, so it may overflow on small screens.
        - Action buttons (delete/cancel/confirm) are small and may be hard to tap on mobile.
        - No fixed widths, but table could still overflow on very narrow screens.
        - All forms/alerts use Bootstrap classes (mobile-friendly).
        - **Proposed Fix:** Wrap table in `.table-responsive` and increase tap target size for action buttons using Bootstrap utilities (e.g., `.w-100`).
      - **Status:** Audit done; remediation complete and tested.
    - [x] `stores.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap table (`.table-striped`) and input group for the add-store form.
        - **Issue:** Table is not wrapped in `.table-responsive`, so it may overflow on small screens.
        - Action buttons (delete/cancel/confirm) are small and may be hard to tap on mobile.
        - No fixed widths, but table could still overflow on very narrow screens.
        - All forms/alerts use Bootstrap classes (mobile-friendly).
        - **Proposed Fix:** Wrap table in `.table-responsive` and increase tap target size for action buttons using Bootstrap utilities (e.g., `.w-100`).
      - **Status:** Audit done; remediation complete and tested.
    - [x] `aisles.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap table (`.table-striped`) and flex form for adding aisles.
        - **Issue:** Table is not wrapped in `.table-responsive`, so it may overflow on small screens.
        - Action buttons (delete/in use) are small and may be hard to tap on mobile.
        - No fixed widths, but table could still overflow on very narrow screens.
        - Alerts and forms use Bootstrap classes (mobile-friendly).
        - **Proposed Fix:** Wrap table in `.table-responsive` and increase tap target size for action buttons using Bootstrap utilities (e.g., `.w-100`).
      - **Status:** Audit done; remediation complete and tested.
    - [x] `master_items.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap input group, form controls, and list group for layout (mobile-friendly).
        - No tables; item list uses vertical `.list-group`, ideal for mobile.
        - **Issue:** Action buttons ("Add to Shopping List") are `.btn-sm` and may be small for tap targets on mobile.
        - No fixed widths detected.
        - **Proposed Fix:** Add `.w-100 w-md-auto` or similar to action buttons for better tap target size on mobile.
      - **Status:** Audit done; remediation complete and tested.
    - [x] `shopping_list.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap table (`.table-striped`) for the shopping list, and a flex form for filtering by store.
        - **Issue:** Table is not wrapped in `.table-responsive`, so it may overflow on small screens. (FIXED)
        - Action buttons (bought/delete) are `.btn-sm` and may be small for tap targets on mobile. (FIXED)
        - No fixed widths, but table could still overflow on very narrow screens. (FIXED)
        - Alerts and forms use Bootstrap classes (mobile-friendly).
        - **Proposed Fix:** Wrap table in `.table-responsive` and increase tap target size for action buttons using Bootstrap utilities (e.g., `.w-100`).
      - **Status:** Audit done; remediation complete and tested.
    - [x] `edit_master_item.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap form controls for all fields, with vertical stacking and spacing (mobile-friendly).
        - Store chips are flexibly laid out; remove buttons are small (styled as icons, not Bootstrap buttons). (FIXED)
        - No tables or fixed widths; layout is fundamentally mobile-friendly.
        - **Issue:** Remove-store buttons ("×") are small and may be hard to tap on mobile. (FIXED)
        - **Proposed Fix:** Increase tap target size for chip remove buttons (e.g., add padding, use Bootstrap `.btn` styles, or wrap in `.btn-sm w-100`).
      - **Status:** Audit done; remediation complete and tested.
    - [x] `family.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap grid (`row`, `col-md-8 mx-auto`) and card/list-group layout for dashboard and members.
        - Member list uses `.list-group` with flex alignment; action buttons are `.btn-sm` and may be small for tap targets on mobile. (FIXED)
        - Invite form uses Bootstrap classes and is mobile-friendly.
        - No tables or fixed widths; layout is fundamentally mobile-friendly.
        - **Issue:** Action buttons (promote/demote) are small and may be hard to tap on mobile. (FIXED)
        - **Proposed Fix:** Increase tap target size for member action buttons (e.g., `.w-100 w-md-auto`).
      - **Status:** Audit done; remediation complete and tested.
    - [x] `user_profile.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap grid (`row`, `col-md-6`, `col-lg-5`) and card layout for profile info.
        - All content is vertically stacked and centered, with good spacing.
        - No tables or fixed widths; layout is fundamentally mobile-friendly.
        - All text and controls are readable and accessible.
        - **Issue:** None found; layout is already mobile-optimized.
      - **Status:** Audit done; no remediation needed.
    - [x] `auth.html`  
      - **Audit (2025-04-26):**
        - Uses Bootstrap grid (`row`, `col-md-6`, `col-lg-5`) and tabbed card layout for login/signup.
        - All forms use `.form-control` and `.w-100` for full-width, mobile-friendly inputs and buttons.
        - No tables or fixed widths; layout is fundamentally mobile-friendly.
        - All text and controls are readable and accessible.
        - **Issue:** None found; layout is already mobile-optimized.
      - **Status:** Audit done; no remediation needed.
- [x] Remediate issues found in each template

### **Testing**
- [x] Audit Playwright tests for mobile viewport coverage
- [x] Add/modify tests as needed
- [x] All automated and UI tests pass as of 2025-04-26. Full suite verified after mobile remediation.
- [x] All Playwright tests for mobile flows (inventory, shopping list, locations, aisles, stores, master items, family) pass.
- [x] No failures or regressions detected.
- [ ] Address SQLAlchemy and Werkzeug deprecation warnings in future technical debt pass.

---

## **Checklist**
- [x] All templates use Bootstrap grid and responsive classes
- [x] No fixed-width or overflowing elements on mobile
- [x] Navbar collapses to hamburger on mobile
- [x] Viewport meta tag present
- [x] All forms and buttons are usable on small screens
- [x] Playwright tests cover mobile viewports

---

## **Progress Log**
- 2025-04-26: Document created, initial findings and plan written. Next steps: add viewport meta tag and refactor navbar.
- 2025-04-26: Viewport meta tag added to base.html and Playwright test added/passed. Next: navbar refactor.
- 2025-04-26: Navbar refactored for Bootstrap mobile collapse and Playwright test added/passed. Next: begin template-by-template mobile audit.

---

## **Next Steps**
1. Review and finalize all template audits and remediations
2. Complete Playwright testing for mobile coverage

---

## Project Management Addendum (Expanded for High-Quality Output)

### 1. Acceptance Criteria & Definition of Done
- The UI must be fully usable on iPhone and Android phones in portrait mode.
- No horizontal scrolling required for any screen.
- All actions (add, edit, delete, navigate) must be accessible and usable with one hand.
- All buttons, inputs, and links must be easily tappable (minimum 44x44px tap target where possible).
- No content should be cut off or require zooming.
- Visual design must remain clean and simple, matching the current desktop style.
- "Done" means the screen passes Playwright mobile viewport tests and a manual check on a phone-sized browser window.

### 2. Template Audit Criteria
For each template:
- Uses Bootstrap grid (`container`, `row`, `col-*`) for layout.
- No fixed widths or overflowing tables/forms.
- Navigation is accessible and collapses appropriately.
- Forms and modals fit within viewport and are scrollable if needed.
- All interactive elements are visible and usable.

### 3. Testing Requirements
- Automated Playwright tests must:
    - Run on at least two mobile viewport sizes (e.g., iPhone 12, Pixel 5).
    - Validate navigation, form interaction, and absence of overflow/horizontal scrolling.
- Manual QA:
    - At least one manual check per screen in Chrome/Firefox mobile emulation.
- Browsers: Chrome and Firefox (Safari is optional but not required at this stage).

### 4. Roles & Responsibilities
- **DEV:** Implements responsive changes, updates Playwright tests, marks tasks as ready for QA.
- **QA:** Runs Playwright and manual checks, documents issues, verifies acceptance criteria.
- **Product:** Reviews screens for usability and consistency, signs off on completion.
- **Project Manager:** Tracks progress, updates this document, ensures blockers are resolved.

### 5. Progress Tracking & Reporting
- Progress log in this document is updated after each major step or screen is completed.
- Weekly check-ins or as needed for blockers.
- All issues/bugs are tracked in this document or the team's preferred issue tracker.

### 6. Communication & Documentation
- All findings, issues, and resolutions are documented in this file for transparency.
- Screenshots or before/after notes can be added if needed for clarity.

### 7. Regression & Maintenance
- Playwright mobile viewport tests are required for all new features going forward.
- Responsive code is reviewed in pull requests.
- Periodic (quarterly) re-audits recommended if the UI changes significantly.

---

## Answers to Expanded Topics (Based on Current Info)

- **Acceptance Criteria:** Defined above. "Mobile-friendly" means no horizontal scrolling, all actions accessible, and all content fits and is usable on phones.
- **Audit Criteria:** Each template must use Bootstrap grid, avoid fixed widths, and be fully usable on a phone. No design or feature changes—only layout/interaction fixes.
- **Testing:** Playwright tests for two mobile viewports, plus a quick manual check in browser emulation. No need for real device lab or Safari testing at this stage.
- **Roles:** DEV makes changes, QA and Product verify, PM tracks and updates this doc.
- **Progress:** This file is the single source of truth for progress and blockers.
- **Communication:** All relevant notes and findings are kept here; no need for extra tools unless the team prefers.
- **Regression:** Playwright mobile tests are the main guard against future breakage.

---

## Scope Reminder
- **Do not** change features, product scope, or visual style.
- **Only** make the app work great on phones using responsive layout and Bootstrap best practices.

---

## Reference:
See the new [User Flow Scenarios](User_Flow_Scenarios.md) document for a detailed description of key user flows and requirements for test development. All UI and E2E tests must follow these flows.

---
