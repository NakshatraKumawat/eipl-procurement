# ==========================================
# CENTRALIZED SYSTEM DATA & HTML INTERFACING
# ==========================================

EMPLOYEE_REGISTRY = [
    {"s_no": 4, "name": "Piyush Bhatia", "designation": "Sr. Manager- Commercial", "contact": "9926306363", "email": "piyush.bhatia@electrainfra.com"},
    {"s_no": 10, "name": "Biswajit Pradhan", "designation": "Engineer", "contact": "9348653235", "email": "b.pradhan@electrainfra.com"},
    {"s_no": 15, "name": "Rahul Sharma", "designation": "Engineer", "contact": "8890609955", "email": "rahul.sharma@electrainfra.com"},
    {"s_no": 19, "name": "Praveen Kumar Bhardwaj", "designation": "General Manager- Mechanical", "contact": "9928364777", "email": "pkb.mech@electrainfra.com"},
    {"s_no": 24, "name": "Nakshatra Kumawat", "designation": "GMT-Commercial", "contact": "8619967694", "email": "n.kumawat@electrainfra.com"},
    {"s_no": 27, "name": "Arun Kumar Jangid", "designation": "OT- Admin", "contact": "9414204535", "email": "arun.jangid@electrainfra.com"},
    {"s_no": 28, "name": "Shaik Sadhik Basha", "designation": "Manager - Operations", "contact": "6378566702", "email": "sadhik.basha@electrainfra.com"}
]

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EIPL System Terminal - Access Verification</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex items-center justify-center font-sans antialiased relative">
    <div class="w-full max-w-md p-8 bg-white rounded-2xl border border-slate-200 shadow-2xl space-y-6 mx-4">
        <div class="text-center space-y-2">
            <div class="mx-auto w-24 mb-2">
                <svg viewBox="0 0 100 40" class="w-full h-auto fill-current text-blue-800 font-black tracking-tighter">
                    <text x="5" y="30" font-family="Arial, Helvetica" font-size="28" font-weight="900">EIPL</text>
                </svg>
            </div>
            <h1 class="text-xl font-extrabold tracking-tight text-slate-900 uppercase">ELECTRA INFRACON PVT LTD
            <p class="text-xs text-slate-500 font-medium">Material & Inventory Control </p>
        </div>
        <form action="/login" method="POST" class="space-y-4 text-xs">
            <div class="space-y-1">
                <label class="block font-semibold text-slate-500 tracking-wide uppercase">User Id</label>
                <input type="text" name="username" required placeholder="Enter User ID" class="w-full bg-slate-100 border border-slate-300 rounded-xl p-3 text-slate-900">
            </div>
            <div class="space-y-1">
                <label class="block font-semibold text-slate-500 tracking-wide uppercase">Password</label>
                <input type="password" name="password" required placeholder="••••••••" class="w-full bg-slate-100 border border-slate-300 rounded-xl p-3 text-slate-900">
            </div>
            <button type="submit" class="w-full bg-indigo-600 text-white font-bold p-3 rounded-xl text-sm">SUBMIT</button>
        </form>
    </div>
</body>
</html>"""


LAYOUT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EIPL Stock Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen antialiased">
    
    <header class="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-md">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-14 h-10 flex items-center justify-center bg-blue-900 text-white rounded-lg font-black text-xl tracking-tighter shadow-sm p-1">
                    EIPL
                </div>
                <div>
                    <h1 class="text-sm font-black tracking-wider text-slate-900 uppercase">EIPL INVENTORY MANAGEMENT SYSTEM</h1>
                    <p class="text-[10px] text-slate-500 font-mono">USER ID: __USER__ [__ROLE__]</p> </div>
            </div>
            <div class="flex items-center gap-4">
                <div class="text-right hidden sm:block">
                    <p class="text-xs font-bold text-slate-700">__USER_FULL_NAME__</p>
                    <p class="text-[10px] text-slate-400 font-medium">__USER_DESIGNATION__ @ __USER_LOCATION__</p>
                </div>
                <a href="/logout" class="bg-rose-600/10 hover:bg-rose-600 border border-rose-600/20 text-rose-600 hover:text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all">Sign Out</a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="space-y-6 lg:col-span-1">
            __ADMIN_PANEL__
            __EMPLOYEE_CONTROL_PANEL__
            __USER_DIRECTORY_CONTROL_PANEL__
            
            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-xl">
                <div class="flex items-center justify-between border-b border-slate-200 pb-2 mb-4">
                    <h2 class="text-xs font-black tracking-wider text-slate-500 uppercase">❖ Record Transaction</h2>
                    <button type="button" onclick="downloadTransactionCSVTemplate()" class="text-[10px] text-indigo-600 hover:underline font-bold">📥 Get Template</button>
                </div>
                <form action="/transaction" method="POST" class="space-y-3 text-xs mb-3">
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Target Asset Entity</label>
                        <select name="item_id" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">__OPTIONS__</select>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-500 mb-1">Transaction</label>
                            <select name="type" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg font-bold">
                                <option value="IN">IN (+ Stock)</option>
                                <option value="OUT">OUT (- Dispatch)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-500 mb-1">Units</label>
                            <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">
                        </div>
                    </div>
                    <button type="submit" class="w-full bg-indigo-600 text-white p-2.5 rounded-lg font-bold">Process Transaction</button>
                </form>
                
                <div class="pt-3 border-t border-dashed border-slate-200">
                    <label class="block font-black text-[10px] uppercase text-emerald-600 mb-1">📊 Bulk Transactions Upload</label>
                    <form action="/transaction/bulk-upload" method="POST" enctype="multipart/form-data" class="flex gap-2">
                        <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border text-[10px] p-1 rounded-lg">
                        <button type="submit" class="bg-emerald-600 text-white px-2 py-1 rounded-lg font-bold text-[10px]">Upload</button>
                    </form>
                    <span class="text-[9px] text-slate-400 italic">Expected columns: Item name, Action, units</span>
                </div>
            </div>

            __PROCUREMENT_WIDGET_PANEL__

            <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-xl">
                <h2 class="text-xs font-black tracking-wider text-slate-500 uppercase border-b border-slate-200 pb-2 mb-4">❖ Material Issue Slip Generator</h2>
                <form action="/material/issue" method="POST" class="space-y-3 text-xs">
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Select Item</label>
                        <select name="item_id" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">__OPTIONS__</select>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-500 mb-1">Quantity</label>
                            <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-500 mb-1">Unit of Measure</label>
                            <input type="text" name="uom" placeholder="e.g. Meters, Nos" required class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-500 mb-1">Issued To (Employee)</label>
                            <select name="issued_to" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">__EMPLOYEE_OPTIONS__</select>
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-500 mb-1">Authorized Dispatched By</label>
                            <input type="text" name="issued_by" value="__USER_FULL_NAME__" readonly class="w-full bg-slate-100 border border-slate-300 text-slate-600 p-2.5 rounded-lg font-medium">
                        </div>
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Remarks / Purpose</label>
                        <input type="text" name="remarks" placeholder="Provide tracking references" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">
                    </div>
                    <button type="submit" class="w-full bg-blue-900 text-white p-2.5 rounded-lg font-bold">Issue Materials</button>
                </form>
            </div>
        </div>

        <div class="space-y-6 lg:col-span-2">
            <div class="bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden">
                <div class="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                    <div>
                        <h2 class="text-xs font-black tracking-wider text-slate-600 uppercase">❖ Inventory Status</h2>
                        <p class="text-[10px] text-slate-400 font-medium">Real-time site stock management</p>
                    </div>
                    <button onclick="downloadInventoryExcel()" class="bg-blue-800 hover:bg-blue-700 text-white font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1">
                        📥 Download Excel
                    </button>
                </div>
                <div class="overflow-x-auto">
                    <table id="inventoryTable" class="w-full text-left border-collapse">
                        <thead class="bg-slate-100 text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                            <tr class="border-b border-slate-200">
                                <th class="p-3">Item Name</th>
                                <th class="p-3">Item Code</th>
                                <th class="p-3">Vendor</th>
                                <th class="p-3">Price</th>
                                <th class="p-3">Current Stock</th>
                                <th class="p-3">Safety Stock</th>
                                <th class="p-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-200 text-slate-700 text-xs">
                            __INVENTORY_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden">
                <div class="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                    <h2 class="text-xs font-black tracking-wider text-slate-600 uppercase">❖ Material Requests</h2>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-slate-100 text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                            <tr class="border-b border-slate-200">
                                <th class="p-3">Date</th>
                                <th class="p-3">Item Description [Dept]</th>
                                <th class="p-3">Req Qty</th>
                                <th class="p-3">Est. Value</th>
                                <th class="p-3">Officer</th>
                                <th class="p-3">Status </th>
                                <th class="p-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-200 text-xs text-slate-700">
                            __REG_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden">
                <div class="p-5 border-b border-slate-200 bg-slate-50">
                    <h2 class="text-xs font-black tracking-wider text-slate-600 uppercase">❖ Material Issue Slip Log</h2>
                </div>
                <div class="overflow-x-auto">
                    <table classRecord Transaction="w-full text-left border-collapse">
                        <thead class="bg-slate-100 text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                            <tr class="border-b border-slate-200">
                                <th class="p-3">Date</th>
                                <th class="p-3">Item Description</th>
                                <th class="p-3">Qty Dispatched</th>
                                <th class="p-3">Receiver</th>
                                <th class="p-3">Issuer </th>
                                <th class="p-3">Remarks</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-200 text-xs text-slate-700">
                            __ASSIGNED_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <div id="procurementModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl">
            <h3 class="text-xs font-black uppercase text-slate-500 tracking-wider border-b pb-2">File Procurement Request</h3>
            <form action="/procurement/request" method="POST" class="space-y-3 text-xs">
                <input type="hidden" id="pro_item_id" name="item_id">
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Item Title</label>
                    <input type="text" id="pro_item_name" readonly class="w-full bg-slate-100 border p-2.5 rounded-lg text-slate-600">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Target Procurement Units</label>
                    <input type="number" name="quantity" min="1" value="5" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Target Department Usage</label>
                    <input type="text" name="department" value="Operations" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('procurementModal').style.display='none'" class="w-1/2 bg-slate-200 text-slate-700 p-2.5 rounded-lg font-bold">Cancel</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 text-white p-2.5 rounded-lg font-bold">Submit Request</button>
                </div>
            </form>
        </div>
    </div>

    <div id="editRequestModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl">
            <h3 class="text-xs font-black uppercase text-slate-500 tracking-wider border-b pb-2">Modify Material Request</h3>
            <form id="editRequestForm" method="POST" class="space-y-3 text-xs">
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Target Inventory Item Entity</label>
                    <select id="edit_req_item_id" name="item_id" class="w-full bg-slate-50 border p-2.5 rounded-lg text-slate-900">
                        __OPTIONS__
                    </select>
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Adjust Quantity</label>
                    <input type="number" id="edit_req_quantity" name="quantity" min="1" required class="w-full bg-slate-50 border p-2.5 rounded-lg text-slate-900">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Update Target Department</label>
                    <input type="text" id="edit_req_department" name="department" required class="w-full bg-slate-50 border p-2.5 rounded-lg text-slate-900">
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('editRequestModal').style.display='none'" class="w-1/2 bg-slate-200 text-slate-700 p-2.5 rounded-lg font-bold">Cancel</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 text-white p-2.5 rounded-lg font-bold">Save Changes</button>
                </div>
            </form>
        </div>
    </div>

    <div id="editModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl">
            <h3 class="text-xs font-black uppercase text-slate-500 tracking-wider border-b pb-2">edit/delete</h3>
            <form id="editForm" method="POST" class="space-y-3 text-xs">
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Asset Nomenclature</label>
                    <input type="text" id="edit_name" name="name" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Item Code</label>
                    <input type="text" id="edit_code" name="item_code" required class="w-full bg-slate-50 border p-2 rounded-lg font-mono">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Linked Storage Site Location</label>
                    <input type="text" id="edit_storage_site" name="storage_site" placeholder="Default Warehouse Site Base" class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">current Stock Level</label>
                        <input type="number" id="edit_stock" name="current_stock" required class="w-full bg-slate-50 border p-2 rounded-lg">
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Minimum Alert Threshold</label>
                        <input type="number" id="edit_min" name="minimum_stock" required class="w-full bg-slate-50 border p-2 rounded-lg">
                    </div>
                </div>
                <div class="flex gap-2 pt-2 border-t mt-4">
                    <button type="button" onclick="document.getElementById('editModal').style.display='none'" class="bg-slate-200 font-bold px-4 py-2 rounded-lg">Close</button>
                    <button type="submit" class="flex-1 bg-indigo-600 text-white font-bold py-2 rounded-lg">Commit System Update</button>
                </div>
            </form>
        </div>
    </div>

    <div id="editUserModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl">
            <h3 class="text-xs font-black uppercase text-slate-500 tracking-wider border-b pb-2">Modify Platform Access Properties</h3>
            <form id="editUserForm" method="POST" class="space-y-3 text-xs">
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Full Legal Name</label>
                    <input type="text" id="edit_user_name" name="full_name" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Designation</label>
                        <input type="text" id="edit_user_desig" name="designation" required class="w-full bg-slate-50 border p-2 rounded-lg">
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Workstation Base</label>
                        <input type="text" id="edit_user_loc" name="workstation_location" required class="w-full bg-slate-50 border p-2 rounded-lg">
                    </div>
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Privilege Mapping</label>
                    <select id="edit_user_role" name="role" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2 rounded-lg font-bold">
                        <option value="Staff">Grant Staff Level</option>
                        <option value="Admin">Grant Full Admin</option>
                    </select>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="closeEditUserModal()" class="w-1/2 bg-slate-200 text-slate-700 p-2.5 rounded-lg font-bold">Cancel</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 text-white p-2.5 rounded-lg font-bold">Save Modifications</button>
                </div>
            </form>
        </div>
    </div>

    <div id="editEmployeeModal" class="fixed inset-0 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl">
            <h3 class="text-xs font-black uppercase text-slate-500 tracking-wider border-b pb-2">Modify Registered Employee Details</h3>
            <form id="editEmployeeForm" method="POST" class="space-y-3 text-xs">
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Employee Name</label>
                    <input type="text" id="edit_emp_name" name="name" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Role Title / Designation</label>
                    <input type="text" id="edit_emp_role" name="role_title" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Workstation Location</label>
                    <input type="text" id="edit_emp_loc" name="location" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Contact Info / Number</label>
                    <input type="text" id="edit_emp_contact" name="contact" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="closeEditEmployeeModal()" class="w-1/2 bg-slate-200 text-slate-700 p-2.5 rounded-lg font-bold">Cancel</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 text-white p-2.5 rounded-lg font-bold">Update Employee</button>
                </div>
            </form>
        </div>
    </div>

    <div id="printTargetFrame" class="hidden font-serif p-10 max-w-2xl mx-auto text-black">
        <div class="text-center space-y-2 border-b pb-4 mb-6">
            <h1 class="text-2xl font-black tracking-tight">ELECTRA INFRASTRUCTURE PVT LTD (EIPL)</h1>
            <p class="text-sm uppercase tracking-widest font-sans text-gray-600">Purchase Order / Procurement Manifest Request</p>
        </div>
        <div class="grid grid-cols-2 gap-4 text-xs mb-6">
            <div><strong>PO Reference ID:</strong> #EIPL-PR-<span id="print_po_id"></span></div>
            <div class="text-right"><strong>Generation Date:</strong> <span id="print_po_date"></span></div>
        </div>
        <table class="w-full text-left text-xs border-collapse border border-black mb-6">
            <thead>
                <tr class="bg-gray-100">
                    <th class="border border-black p-2">Asset Material Nomenculture</th>
                    <th class="border border-black p-2">Item Code</th>
                    <th class="border border-black p-2 text-right">Units Requested</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td id="print_po_name" class="border border-black p-2 font-bold"></td>
                    <td id="print_po_code" class="border border-black p-2 font-mono"></td>
                    <td id="print_po_qty" class="border border-black p-2 text-right font-bold"></td>
                </tr>
            </tbody>
        </table>
        <div class="text-right text-xs mt-16 font-sans">
            <div class="inline-block border-t border-black pt-2 px-6">Authorized Logistics Lead Signature</div>
        </div>
    </div>

    <script>
        function openProcurementModal(id, name) {
            document.getElementById('pro_item_id').value = id;
            document.getElementById('pro_item_name').value = name;
            document.getElementById('procurementModal').style.display = 'flex';
        }
        function openEditRequestModal(id, quantity, department, itemId) {
            document.getElementById('editRequestForm').action = '/procurement/edit/' + id;
            document.getElementById('edit_req_quantity').value = quantity;
            document.getElementById('edit_req_department').value = department;
            if (document.getElementById('edit_req_item_id')) {
                document.getElementById('edit_req_item_id').value = itemId || '';
            }
            document.getElementById('editRequestModal').style.display = 'flex';
        }
        function openEditUserModal(id, name, designation, location, role) {
            document.getElementById('editUserForm').action = '/admin/users/edit/' + id;
            document.getElementById('edit_user_name').value = name;
            document.getElementById('edit_user_desig').value = designation;
            document.getElementById('edit_user_loc').value = location;
            document.getElementById('edit_user_role').value = role;
            document.getElementById('editUserModal').style.display = 'flex';
        }
        function closeEditUserModal() { document.getElementById('editUserModal').style.display = 'none'; }
        
        function openEditEmployeeModal(id, name, role, loc, contact) {
            document.getElementById('editEmployeeForm').action = '/employees/edit/' + id;
            document.getElementById('edit_emp_name').value = name;
            document.getElementById('edit_emp_role').value = role;
            document.getElementById('edit_emp_loc').value = loc;
            document.getElementById('edit_emp_contact').value = contact;
            document.getElementById('editEmployeeModal').style.display = 'flex';
        }
        function closeEditEmployeeModal() { document.getElementById('editEmployeeModal').style.display = 'none'; }

        function triggerInlinePOPrint(id, itemName, itemCode, quantity) {
            document.getElementById('print_po_id').innerText = id;
            document.getElementById('print_po_date').innerText = new Date().toLocaleDateString('en-IN');
            document.getElementById('print_po_name').innerText = itemName;
            document.getElementById('print_po_code').innerText = itemCode;
            document.getElementById('print_po_qty').innerText = quantity;
            
            const originalContent = document.body.innerHTML;
            const printLayout = document.getElementById('printTargetFrame').innerHTML;
            
            document.body.innerHTML = printLayout;
            window.print();
            document.body.innerHTML = originalContent;
            window.location.reload();
        }

        function downloadTransactionCSVTemplate() {
            var csvContent = "Item name,Action,units\\nSteel Pipe,IN,50\\nCement Bags,OUT,10";
            triggerCSVBlobDownload("EIPL_Transaction_Bulk_Template.csv", csvContent);
        }

        function downloadItemsCSVTemplate() {
            var csvContent = "name,item_code,initial_stock,price,vendor,site\\nStructural Beam,EIPL-BM-01,100,2450.00,Tata Steel,Udaipur Site\\nCopper Wire,EIPL-WR-09,500,120.00,Havells,Corporate HQ";
            triggerCSVBlobDownload("EIPL_Item_Registry_Bulk_Template.csv", csvContent);
        }

        function triggerCSVBlobDownload(filename, text) {
            var blob = new Blob([text], {type: "text/csv;charset=utf-8;"});
            var element = document.createElement("a");
            element.setAttribute("href", window.URL.createObjectURL(blob));
            element.setAttribute("download", filename);
            element.style.display = "none";
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        }

        function downloadInventoryExcel() {
            var csv = [];
            var rows = document.querySelectorAll("#inventoryTable tr");
            for (var i = 0; i < rows.length; i++) {
                var row = [], cols = rows[i].querySelectorAll("td, th");
                for (var j = 0; j < cols.length - 1; j++) {
                    var cleanText = cols[j].innerText.replace(/\\n/g, '').replace(/⚠️ LOW/g, '').trim();
                    row.push('"' + cleanText.replace(/"/g, '""') + '"');
                }
                csv.push(row.join(","));
            }
            triggerCSVBlobDownload("EIPL_Current_Stock_Report.csv", csv.join("\\n"));
        }
    </script>
</body>
</html>"""