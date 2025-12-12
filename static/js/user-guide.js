/**
 * Atlas CRM - User Guide System
 * Provides interactive guided tours and help popups for each module
 */

class AtlasUserGuide {
    constructor() {
        this.guides = {
            dashboard: {
                title: 'Dashboard Overview',
                icon: 'fa-tachometer-alt',
                steps: [
                    { title: 'Welcome Widget', description: 'View your login status and quick system overview at a glance.' },
                    { title: 'Key Metrics', description: 'Monitor Total Sales, Active Users, System Alerts, and Performance metrics in real-time.' },
                    { title: 'Activity Charts', description: 'Analyze user activity and system performance trends over time.' },
                    { title: 'Drilldown Reports', description: 'Click on any report card to access detailed analytics and data.' },
                    { title: 'Quick Actions', description: 'Use the sidebar to navigate to any module quickly.' }
                ]
            },
            orders: {
                title: 'Order Management',
                icon: 'fa-shopping-cart',
                steps: [
                    { title: 'Create Orders', description: 'Click "Add Order" to create new orders manually with customer details, products, and payment method.' },
                    { title: 'Bulk Import', description: 'Use "Bulk Import" to upload multiple orders via CSV/Excel template.' },
                    { title: 'Order Status', description: 'Track orders through: Pending → Confirmed → Packaging → Ready for Delivery → Delivered.' },
                    { title: 'Filter & Search', description: 'Use filters to find orders by status, date, customer, or order number.' },
                    { title: 'Order Actions', description: 'Click on any order to view details, edit, or update its status.' }
                ]
            },
            inventory: {
                title: 'Inventory Management',
                icon: 'fa-boxes',
                steps: [
                    { title: 'Stock Overview', description: 'View current stock levels, low stock alerts, and inventory value.' },
                    { title: 'Product Locations', description: 'Each product is assigned to a warehouse location (Rack/Row/Shelf).' },
                    { title: 'Stock Adjustments', description: 'Record stock in, stock out, and adjustments with reasons.' },
                    { title: 'Activity Log', description: 'View complete history of all inventory movements and changes.' },
                    { title: 'Low Stock Alerts', description: 'System automatically alerts when stock falls below minimum levels.' }
                ]
            },
            products: {
                title: 'Product Management',
                icon: 'fa-box',
                steps: [
                    { title: 'Add Products', description: 'Create new products with SKU, name, barcode, category, and pricing.' },
                    { title: 'Barcode Generation', description: 'System auto-generates unique barcodes for each product.' },
                    { title: 'Product Categories', description: 'Organize products into categories for easy management.' },
                    { title: 'Pricing & Cost', description: 'Set cost price, selling price, and track profit margins.' },
                    { title: 'Product Images', description: 'Upload product images for visual identification.' }
                ]
            },
            sourcing: {
                title: 'Sourcing Requests',
                icon: 'fa-truck-loading',
                steps: [
                    { title: 'Create Request', description: 'Submit sourcing requests with product details, quantity, and funding source.' },
                    { title: 'Funding Source', description: 'Select "Company Funds" or "Seller Funds" - this links to the Finance module.' },
                    { title: 'Approval Workflow', description: 'Requests go through: Pending → Approved/Rejected → In Transit → Received.' },
                    { title: 'Auto-Assignment', description: 'Upon approval, system auto-assigns warehouse location and generates barcode.' },
                    { title: 'Track Shipments', description: 'Monitor sourcing request status and expected delivery dates.' }
                ]
            },
            callcenter: {
                title: 'Call Center Module',
                icon: 'fa-headset',
                steps: [
                    { title: 'Order Queue', description: 'View "Pending Confirmation" orders assigned to you or available for pickup.' },
                    { title: 'Auto-Assign', description: 'Managers can use auto-assign to distribute orders evenly among agents.' },
                    { title: 'Call Logging', description: 'Log call duration and outcomes for each customer contact.' },
                    { title: 'Status Updates', description: 'Update order status: Confirmed, No Answer, Postponed, or Escalate.' },
                    { title: 'Follow-up Scheduling', description: 'Set callback dates for postponed orders - system will remind you.' }
                ]
            },
            packaging: {
                title: 'Pick & Pack Module',
                icon: 'fa-box-open',
                steps: [
                    { title: 'Pending Orders', description: 'View orders with status "Pending Packaging" ready for fulfillment.' },
                    { title: 'Pick List', description: 'See product locations and quantities to pick from warehouse.' },
                    { title: 'Start Picking', description: 'Click "Start Picking" to begin the fulfillment process.' },
                    { title: 'Select Packaging', description: 'Choose packaging type - system tracks material inventory.' },
                    { title: 'Complete Packing', description: 'Click "Finish Packing" - stock is auto-deducted and status updates.' }
                ]
            },
            delivery: {
                title: 'Delivery Management',
                icon: 'fa-shipping-fast',
                steps: [
                    { title: 'Assignment Queue', description: 'View orders "Ready for Delivery Assignment" waiting for drivers.' },
                    { title: 'Assign Drivers', description: 'Assign orders to available delivery agents based on route/area.' },
                    { title: 'Agent Updates', description: 'Agents update status: Delivered, Failed, or Returned.' },
                    { title: 'Manager Confirmation', description: 'All agent updates require manager confirmation before final status.' },
                    { title: 'COD Collection', description: 'Track COD cash collection from agents for reconciliation.' }
                ]
            },
            finance: {
                title: 'Finance & Accounting',
                icon: 'fa-file-invoice-dollar',
                steps: [
                    { title: 'Fee Settings', description: 'Configure default fees: Service, Fulfillment, Delivery, and custom fees.' },
                    { title: 'Invoices', description: 'Generate invoices for services rendered and COD settlements.' },
                    { title: 'Vendor Credits', description: 'Manage seller credit balances when using company funds.' },
                    { title: 'COD Reconciliation', description: 'Reconcile COD cash collected by delivery agents.' },
                    { title: 'Payouts', description: 'Process seller payouts with proof of payment uploads.' }
                ]
            },
            sellers: {
                title: 'Seller Management',
                icon: 'fa-store',
                steps: [
                    { title: 'Seller List', description: 'View all registered sellers/vendors with their status and balance.' },
                    { title: 'Add Seller', description: 'Create new seller accounts with company and contact details.' },
                    { title: 'Credit Balance', description: 'View and manage seller credit balance for company-funded sourcing.' },
                    { title: 'Seller Products', description: 'View products associated with each seller.' },
                    { title: 'Performance Metrics', description: 'Track seller order volume, revenue, and performance.' }
                ]
            },
            users: {
                title: 'User Management',
                icon: 'fa-users-cog',
                steps: [
                    { title: 'User List', description: 'View all internal users with their roles and status.' },
                    { title: 'Create User', description: 'Add new internal users with role assignment (Super Admin only).' },
                    { title: 'Role Assignment', description: 'Assign predefined roles: Admin, Manager, Agent, Stock Keeper, etc.' },
                    { title: 'Password Reset', description: 'Reset user passwords - they must change on first login.' },
                    { title: 'Deactivate Users', description: 'Deactivate users to revoke access without deleting.' }
                ]
            },
            roles: {
                title: 'Roles & Permissions',
                icon: 'fa-user-shield',
                steps: [
                    { title: 'Role List', description: 'View all system roles and the number of users assigned.' },
                    { title: 'Create Role', description: 'Create custom roles with specific permissions (Super Admin only).' },
                    { title: 'Permission Matrix', description: 'Check/uncheck permissions for each module and action.' },
                    { title: 'Edit Permissions', description: 'Modify existing role permissions as business needs change.' },
                    { title: 'Access Control', description: 'Permissions are enforced on both UI and API level.' }
                ]
            },
            subscribers: {
                title: 'Subscriber Approvals',
                icon: 'fa-user-clock',
                steps: [
                    { title: 'Pending Queue', description: 'View self-registered sellers awaiting admin approval.' },
                    { title: 'Review Details', description: 'Check company info, contact details, and expected order volume.' },
                    { title: 'Approve', description: 'Approve to create seller account and send welcome email.' },
                    { title: 'Reject', description: 'Reject with reason - applicant receives notification email.' },
                    { title: 'Email Notifications', description: 'System sends automated emails for approval/rejection.' }
                ]
            },
            returns: {
                title: 'Return Management',
                icon: 'fa-undo-alt',
                steps: [
                    { title: 'Return List', description: 'View all returned orders with status and reason.' },
                    { title: 'Process Return', description: 'Log return reason and classify item condition.' },
                    { title: 'Sellable Items', description: 'Items marked sellable are returned to available inventory.' },
                    { title: 'Damaged Items', description: 'Damaged items are logged separately and removed from sellable stock.' },
                    { title: 'Stock Updates', description: 'System automatically updates inventory based on return classification.' }
                ]
            }
        };

        this.currentModule = this.detectCurrentModule();
        this.isGuideEnabled = this.getGuidePreference();
        this.init();
    }

    detectCurrentModule() {
        const path = window.location.pathname;
        if (path.includes('/dashboard')) return 'dashboard';
        if (path.includes('/orders/returns')) return 'returns';
        if (path.includes('/orders')) return 'orders';
        if (path.includes('/inventory')) return 'inventory';
        if (path.includes('/products')) return 'products';
        if (path.includes('/sourcing')) return 'sourcing';
        if (path.includes('/callcenter')) return 'callcenter';
        if (path.includes('/packaging')) return 'packaging';
        if (path.includes('/delivery')) return 'delivery';
        if (path.includes('/finance')) return 'finance';
        if (path.includes('/sellers')) return 'sellers';
        if (path.includes('/users')) return 'users';
        if (path.includes('/roles')) return 'roles';
        if (path.includes('/subscribers')) return 'subscribers';
        return 'dashboard';
    }

    getGuidePreference() {
        const pref = localStorage.getItem('atlasGuideEnabled');
        return pref === null ? true : pref === 'true';
    }

    setGuidePreference(enabled) {
        localStorage.setItem('atlasGuideEnabled', enabled);
        this.isGuideEnabled = enabled;
    }

    init() {
        this.createGuideElements();
        this.attachEventListeners();

        // Show guide automatically on first visit to a module
        const visitedModules = JSON.parse(localStorage.getItem('atlasVisitedModules') || '[]');
        if (this.isGuideEnabled && !visitedModules.includes(this.currentModule)) {
            setTimeout(() => this.showGuide(), 1500);
            visitedModules.push(this.currentModule);
            localStorage.setItem('atlasVisitedModules', JSON.stringify(visitedModules));
        }
    }

    createGuideElements() {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'guide-overlay';
        overlay.id = 'guideOverlay';
        document.body.appendChild(overlay);

        // Create popup
        const popup = document.createElement('div');
        popup.className = 'guide-popup';
        popup.id = 'guidePopup';
        document.body.appendChild(popup);

        // Create trigger button
        const trigger = document.createElement('button');
        trigger.className = 'guide-trigger';
        trigger.id = 'guideTrigger';
        trigger.innerHTML = '<i class="fas fa-question"></i>';
        trigger.title = 'Help & Guide';
        document.body.appendChild(trigger);

        this.renderGuideContent();
    }

    renderGuideContent() {
        const guide = this.guides[this.currentModule] || this.guides.dashboard;
        const popup = document.getElementById('guidePopup');

        popup.innerHTML = `
            <div class="guide-header">
                <h3><i class="fas ${guide.icon}" style="margin-right: 10px;"></i>${guide.title}</h3>
                <button class="guide-close" id="guideClose">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="guide-content">
                ${guide.steps.map((step, index) => `
                    <div class="guide-step">
                        <div class="guide-step-number">${index + 1}</div>
                        <div class="guide-step-content">
                            <h4>${step.title}</h4>
                            <p>${step.description}</p>
                        </div>
                    </div>
                `).join('')}
            </div>
            <div class="guide-footer">
                <label class="guide-toggle-label">
                    <input type="checkbox" id="guideAutoShow" ${this.isGuideEnabled ? 'checked' : ''}>
                    Show guide on first visit to each module
                </label>
                <button class="btn-modern btn-modern-primary" id="guideGotIt">Got it!</button>
            </div>
        `;
    }

    attachEventListeners() {
        document.getElementById('guideTrigger').addEventListener('click', () => this.showGuide());
        document.getElementById('guideOverlay').addEventListener('click', () => this.hideGuide());

        document.addEventListener('click', (e) => {
            if (e.target.id === 'guideClose' || e.target.closest('#guideClose')) {
                this.hideGuide();
            }
            if (e.target.id === 'guideGotIt' || e.target.closest('#guideGotIt')) {
                this.hideGuide();
            }
            if (e.target.id === 'guideAutoShow') {
                this.setGuidePreference(e.target.checked);
            }
        });

        // Keyboard shortcut: Press '?' to show guide
        document.addEventListener('keydown', (e) => {
            if (e.key === '?' && !e.ctrlKey && !e.altKey && !e.metaKey) {
                const activeElement = document.activeElement;
                if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
                    e.preventDefault();
                    this.showGuide();
                }
            }
            if (e.key === 'Escape') {
                this.hideGuide();
            }
        });
    }

    showGuide() {
        this.renderGuideContent(); // Re-render in case module changed
        document.getElementById('guideOverlay').classList.add('active');
        document.getElementById('guidePopup').classList.add('active');
    }

    hideGuide() {
        document.getElementById('guideOverlay').classList.remove('active');
        document.getElementById('guidePopup').classList.remove('active');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize on authenticated pages (not landing/login)
    if (!document.body.classList.contains('landing-page') &&
        !window.location.pathname.includes('/login') &&
        !window.location.pathname.includes('/register')) {
        window.atlasGuide = new AtlasUserGuide();
    }
});
