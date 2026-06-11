# =========================================================================
# CENTRALIZED SYSTEM DATA & MODERN LIGHT ENTERPRISE UI (Tailwind CSS)
# =========================================================================

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
    <title>EIPL Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen relative overflow-hidden">
    <div class="absolute w-[500px] h-[500px] bg-indigo-500/5 rounded-full blur-3xl top-[-10%] left-[-10%]"></div>
    <div class="absolute w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-3xl bottom-[-10%] right-[-10%]"></div>

    <div class="w-full max-w-md bg-white border border-slate-200 p-8 rounded-2xl shadow-xl relative z-10 mx-4">
        <div class="text-center mb-8">
            <span class="bg-indigo-50 text-indigo-600 font-semibold text-xs uppercase tracking-wider px-3 py-1 rounded-full border border-indigo-100">
                Enterprise Portal
            </span>
            <h1 class="text-2xl font-bold text-slate-900 mt-4 tracking-tight">Electra Infracon Pvt Ltd</h1>
            <p class="text-slate-500 text-sm mt-1">Material & Inventory Control</p>
        </div>
        
        <form action="/login" method="POST" class="space-y-5">
            <div>
                <label class="block text-slate-700 text-xs font-semibold uppercase tracking-wider mb-2">User Id</label>
                <input type="text" name="username" required autocomplete="off" placeholder="Enter User ID"
                       class="w-full bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 px-4 py-3 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white transition-all text-sm shadow-sm">
            </div>
            <div>
                <label class="block text-slate-700 text-xs font-semibold uppercase tracking-wider mb-2">Password</label>
                <input type="password" name="password" required placeholder="••••••••"
                       class="w-full bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400 px-4 py-3 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white transition-all text-sm shadow-sm">
            </div>
            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-medium tracking-wide transition-all shadow-md shadow-indigo-600/10 text-sm font-semibold mt-2">
                SUBMIT
            </button>
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { font-family: 'Inter', sans-serif; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #f1f5f9; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex">

    <aside class="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0 shadow-sm z-20">
        <div class="p-6 border-b border-slate-100">
            <div class="flex items-center gap-3">
                <div class="bg-indigo-600 px-3 py-2 rounded-xl text-white shadow-md shadow-indigo-600/20 font-black tracking-tighter text-sm">
                    EIPL
                </div>
                <div class="min-w-0">
                    <h2 class="font-bold text-slate-900 tracking-tight text-sm leading-tight uppercase truncate">Electra Infracon</h2>
                    <p class="text-[10px] text-slate-400 font-mono mt-0.5 truncate">UID: __USER__</p>
                </div>
            </div>
        </div>

        <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2 font-semibold">Core Dashboard</p>
            
            <button id="nav-inventory" onclick="switchTab('inventory')" class="w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left">
                <i class="fa-solid fa-boxes-stacked w-5 text-center text-indigo-600"></i> Inventory Status
            </button>
            
            <button id="nav-requisitions" onclick="switchTab('requisitions')" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all text-left group">
                <i class="fa-solid fa-file-invoice-dollar w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Requisitions
            </button>
            
            <button id="nav-allocations" onclick="switchTab('allocations')" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all text-left group">
                <i class="fa-solid fa-truck-ramp-box w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Allocations
            </button>

            <div class="pt-4 mt-4 border-t border-slate-100 space-y-1">
                <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2 font-semibold">Administration</p>
                <button onclick="openEmployeeModal()" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-lg text-xs font-medium transition-all text-left group">
                    <i class="fa-solid fa-user-plus w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> Employee Registry
                </button>
                <button onclick="openAccessModal()" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-lg text-xs font-medium transition-all text-left group">
                    <i class="fa-solid fa-key w-4 text-center text-slate-400 group-hover:text-emerald-600"></i> Grant User Access
                </button>
                <a href="/grn/list" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-lg text-xs font-medium transition-all text-left group">
                    <i class="fa-solid fa-download w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> GRN Download Centre
                </a>
                <a href="/mis/list" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-lg text-xs font-medium transition-all text-left group">
                    <i class="fa-solid fa-file-arrow-down w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> MIS Download Centre
                </a>
            </div>
        </nav>

        <div class="p-4 border-t border-slate-100 bg-slate-50/50">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2.5 min-w-0">
                    <div class="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center font-bold text-[11px] text-indigo-700 shrink-0 uppercase">
                        __ROLE__[0]
                    </div>
                    <div class="min-w-0">
                        <h4 class="text-xs font-bold text-slate-900 leading-none truncate">__USER_FULL_NAME__</h4>
                        <span class="text-[10px] text-slate-400 mt-0.5 inline-block truncate max-w-[120px]">__USER_DESIGNATION__</span>
                    </div>
                </div>
                <a href="/logout" class="text-slate-400 hover:text-rose-600 transition-colors p-1.5 rounded-lg hover:bg-rose-50" title="Sign Out">
                    <i class="fa-solid fa-right-from-bracket text-xs"></i>
                </a>
            </div>
            <div class="bg-white p-2 rounded-lg text-[10px] text-slate-500 space-y-0.5 border border-slate-200 shadow-sm">
                <div><span class="text-slate-400 font-medium">Station:</span> __USER_LOCATION__</div>
            </div>
        </div>
    </aside>

    <main class="flex-1 flex flex-col overflow-x-hidden">
        <header class="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shrink-0 shadow-sm z-10">
            <div class="flex items-center gap-2 text-xs font-semibold text-slate-400">
                <span class="uppercase tracking-wider text-indigo-600 font-bold">EIPL Framework</span>
                <i class="fa-solid fa-chevron-right text-[9px] text-slate-300"></i>
                <span id="header-breadcrumb" class="text-slate-700 font-medium">Inventory Status Dashboard</span>
            </div>
        </header>

        <div class="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1650px] w-full mx-auto">
            
            <div id="tab-viewport-inventory" class="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                
                <div class="xl:col-span-1 space-y-6">
                    __ADMIN_PANEL__
                    
                    <div class="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm space-y-4">
                        <div class="flex items-center justify-between border-b border-slate-100 pb-3">
                            <div>
                                <h3 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Inward Transaction</h3>
                                <p class="text-[10px] text-slate-400 mt-0.5">Record incoming materials — GRN upload mandatory</p>
                            </div>
                            <button type="button" onclick="downloadTransactionCSVTemplate()" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-100 px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all flex items-center gap-1 shadow-sm">
                                <i class="fa-solid fa-download"></i> Template
                            </button>
                        </div>
                        
                        <form action="/transaction" method="POST" enctype="multipart/form-data" class="space-y-4 text-xs text-slate-700">
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Select Item</label>
                                <select name="item_id" class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">__OPTIONS__</select>
                            </div>
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block font-semibold text-slate-600 mb-1.5">Quantity Received</label>
                                    <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm font-mono font-semibold">
                                </div>
                                <div>
                                    <label class="block font-semibold text-slate-600 mb-1.5">Unit of Measure</label>
                                    <select name="uom" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
                                        <option value="Nos">Nos — Numbers</option>
                                        <option value="Mtr">Mtr — Metres</option>
                                        <option value="Kg">Kg — Kilograms</option>
                                        <option value="Ltr">Ltr — Litres</option>
                                        <option value="Set">Set</option>
                                        <option value="Pair">Pair</option>
                                        <option value="Box">Box</option>
                                        <option value="Roll">Roll</option>
                                        <option value="Bag">Bag</option>
                                        <option value="Ton">Ton</option>
                                        <option value="Sqm">Sqm — Sq. Metres</option>
                                        <option value="Rmt">Rmt — Running Metres</option>
                                        <option value="Lot">Lot</option>
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Upload GRN <span class="text-rose-500 font-black">*</span></label>
                                <input type="file" name="grn_file" required accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx"
                                    class="w-full bg-rose-50 border border-rose-200 text-slate-700 text-[11px] p-2 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
                                <p class="text-[10px] text-rose-500 mt-1 font-medium">⚠ GRN must be uploaded to proceed</p>
                            </div>
                            <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all shadow-md shadow-emerald-600/10">
                                ✓ Record Inward & Upload GRN
                            </button>
                        </form>
                        <div class="pt-4 border-t border-dashed border-slate-200">
                            <label class="block font-bold text-[10px] uppercase text-emerald-700 mb-2 tracking-wider flex items-center gap-1">📊 Bulk Transactions Upload</label>
                            <form action="/transaction/bulk-upload" method="POST" enctype="multipart/form-data" class="flex gap-2">
                                <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border border-slate-200 text-slate-600 text-[10px] p-2 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
                                <button type="submit" class="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-xl font-bold text-[10px] tracking-wide transition-all shrink-0 shadow-sm">Upload</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="xl:col-span-2">
                    <div id="inventory-table-container" class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                        <div class="p-5 border-b border-slate-100 bg-white flex items-center justify-between gap-4">
                            <div>
                                <h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Consolidated Inventory Status</h2>
                                <p class="text-[10px] text-slate-400 mt-0.5">Real-time warehouse material mapping and safety levels</p>
                            </div>
                            <button onclick="downloadInventoryExcel()" class="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm">
                                <i class="fa-solid fa-file-excel"></i> Export Matrix
                            </button>
                        </div>
                        <div class="overflow-x-auto">
                            <table id="inventoryTable" class="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase border-b border-slate-200">
                                        <th class="p-4 pl-5">Item Name</th>
                                        <th class="p-4">Item Code</th>
                                        <th class="p-4 admin-only-col">Vendor</th>
                                        <th class="p-4 admin-only-col">Price</th>
                                        <th class="p-4 text-center">Current Stock</th>
                                        <th class="p-4 text-center">Safety Stock</th>
                                        <th class="p-4 text-right pr-5">Actions</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100 font-medium text-slate-700">
                                    __INVENTORY_ROWS__
                                </tbody>
                            </table>
                        </div>
                        <script>
                        (function(){
                            var isAdmin = __IS_ADMIN__;
                            if (!isAdmin) {
                                document.querySelectorAll('.admin-only-col').forEach(function(el){ el.style.display='none'; });
                            }
                        })();
                        </script>
                    </div>
                </div>
            </div>

            <div id="tab-viewport-requisitions" class="hidden grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                
                <div class="xl:col-span-1">
                    __PROCUREMENT_WIDGET_PANEL__
                </div>

                <div class="xl:col-span-2">
                    <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                        <div class="p-5 border-b border-slate-100 bg-white">
                            <h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Procurement Pipeline Indents</h2>
                            <p class="text-[10px] text-slate-400 mt-0.5">Formal procurement intent registries and operations pipeline tracker</p>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase border-b border-slate-200">
                                        <th class="p-3 pl-5 whitespace-nowrap">Time Stamp</th>
                                        <th class="p-3">Item Description</th>
                                        <th class="p-3 text-center">Qty</th>
                                        <th class="p-3 text-right whitespace-nowrap">Est. Value</th>
                                        <th class="p-3">Item Code</th>
                                        <th class="p-3">Specification</th>
                                        <th class="p-3 whitespace-nowrap">Requested By</th>
                                        <th class="p-3 text-center">Status</th>
                                        <th class="p-3">Communication</th>
                                        <th class="p-3 text-right pr-5 whitespace-nowrap">Workflow</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100 font-medium text-slate-700">
                                    __REG_ROWS__
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <div id="tab-viewport-allocations" class="hidden grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                
                <div class="xl:col-span-1">
                    <div class="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm space-y-4">
                        <div>
                            <h3 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Material Issue Slip</h3>
                            <p class="text-[10px] text-slate-400 mt-0.5">Issue procured materials — MIS upload mandatory to proceed</p>
                        </div>
                        
                        <form action="/material/issue" method="POST" enctype="multipart/form-data" class="space-y-4 text-xs text-slate-700 border-t border-slate-100 pt-3">
                            <!-- ITEM SEARCH BOX -->
                            <div class="relative">
                                <label class="block font-semibold text-slate-600 mb-1.5">Search & Select Item</label>
                                <input type="text" id="mis_item_search" placeholder="Type item name or code..." autocomplete="off"
                                    class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm"
                                    oninput="filterMISItems(this.value)" onfocus="showMISDropdown()" />
                                <div id="mis_item_dropdown" class="absolute z-30 w-full bg-white border border-slate-200 rounded-xl shadow-xl mt-1 max-h-48 overflow-y-auto hidden"></div>
                                <input type="hidden" id="mis_item_id" name="item_id" required />
                                <p id="mis_selected_item_label" class="text-[10px] text-indigo-600 font-semibold mt-1 hidden"></p>
                            </div>

                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <label class="block font-semibold text-slate-600 mb-1.5">Issue Quantity</label>
                                    <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm font-mono font-semibold">
                                </div>
                                <div>
                                    <label class="block font-semibold text-slate-600 mb-1.5">Unit (UOM)</label>
                                    <select name="uom" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
                                        <option value="Nos">Nos — Numbers</option>
                                        <option value="Mtr">Mtr — Metres</option>
                                        <option value="Kg">Kg — Kilograms</option>
                                        <option value="Ltr">Ltr — Litres</option>
                                        <option value="Set">Set</option>
                                        <option value="Pair">Pair</option>
                                        <option value="Box">Box</option>
                                        <option value="Roll">Roll</option>
                                        <option value="Bag">Bag</option>
                                        <option value="Ton">Ton</option>
                                        <option value="Sqm">Sqm — Sq. Metres</option>
                                        <option value="Rmt">Rmt — Running Metres</option>
                                        <option value="Lot">Lot</option>
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Issued To</label>
                                <select name="issued_to" class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm font-medium">__EMPLOYEE_OPTIONS__</select>
                            </div>
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Department</label>
                                <input type="text" name="department" placeholder="e.g. Mechanical, Electrical, Operations" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
                            </div>
                            <input type="hidden" name="issued_by" value="__USER__">
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Field Remarks</label>
                                <input type="text" name="remarks" placeholder="Purpose or site reference" class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
                            </div>
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Upload MIS <span class="text-rose-500 font-black">*</span></label>
                                <input type="file" name="mis_file" required accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx"
                                    class="w-full bg-rose-50 border border-rose-200 text-slate-700 text-[11px] p-2 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
                                <p class="text-[10px] text-rose-500 mt-1 font-medium">&#9888; MIS must be uploaded to proceed with issuance</p>
                            </div>
                            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all shadow-md shadow-indigo-600/10">
                                &#10003; Authorize Issue &amp; Upload MIS
                            </button>
                        </form>
                    </div>
                </div>

                <div class="xl:col-span-2">
                    <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                        <div class="p-5 border-b border-slate-100 bg-white">
                            <h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Physical Asset Allocations Journal</h2>
                            <p class="text-[10px] text-slate-400 mt-0.5">Permanent deployment records and site field custodian mapping</p>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase border-b border-slate-200">
                                        <th class="p-4 pl-5">Date &amp; Time</th>
                                        <th class="p-4">Item Name</th>
                                        <th class="p-4 text-center">Quantity</th>
                                        <th class="p-4 text-center">UOM</th>
                                        <th class="p-4">Issued To</th>
                                        <th class="p-4">Department</th>
                                        <th class="p-4 pr-5">Remarks</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100 font-medium text-slate-700">
                                    __ASSIGNED_ROWS__
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    </main>

    <div id="employeeRegistrationModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl text-slate-800 relative">
            <button onclick="closeEmployeeModal()" class="absolute top-4 right-4 text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark"></i></button>
            __EMPLOYEE_CONTROL_PANEL__
        </div>
    </div>

    <div id="grantAccessModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl text-slate-800 relative">
            <button onclick="closeAccessModal()" class="absolute top-4 right-4 text-slate-400 hover:text-slate-600"><i class="fa-solid fa-xmark"></i></button>
            __USER_DIRECTORY_CONTROL_PANEL__
        </div>
    </div>

    <div id="editItemModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div id="editItemModalContent" class="bg-white border border-slate-200 p-6 rounded-2xl max-w-lg w-full space-y-4 shadow-2xl text-slate-800"></div>
    </div>

    <div id="editRequestModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl text-slate-800">
            <h3 class="text-xs font-bold uppercase text-slate-900 tracking-wider border-b border-slate-100 pb-3">Modify Material Request</h3>
            <form id="editRequestForm" method="POST" class="space-y-4 text-xs text-slate-700">
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Target Inventory Item Entity</label>
                    <select id="edit_req_item_id" name="item_id" class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 shadow-sm">__OPTIONS__</select>
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Adjust Quantity</label>
                    <input type="number" id="edit_req_quantity" name="quantity" min="1" required class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 font-mono font-semibold shadow-sm">
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Update Target Department</label>
                    <input type="text" id="edit_req_department" name="department" required class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 shadow-sm">
                </div>
                <div class="flex gap-3 pt-2">
                    <button type="button" onclick="closeEditRequestModal()" class="w-1/2 bg-slate-100 hover:bg-slate-200 text-slate-700 p-2.5 rounded-xl font-bold transition-all border border-slate-200 shadow-sm">Cancel</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-xl font-bold transition-all shadow-md shadow-indigo-600/10">Save Modifications</button>
                </div>
            </form>
        </div>
    </div>

    <script id="mis-inventory-data" type="application/json">__MIS_INVENTORY_JSON__</script>
    <script>
        // ---- GLOBAL DELEGATED EVENT HANDLER (safe data-* approach, no onclick string injection) ----
        document.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-action]');
            if (!btn) return;
            var action = btn.dataset.action;
            var d = btn.dataset;

            if (action === 'procure') {
                openProcurementModal(d.id, d.name, d.code);
            } else if (action === 'edit-item') {
                openEditItemModal(d.id, d.name, d.code, d.price, d.stock, d.minstock);
            } else if (action === 'edit-request') {
                openEditRequestModal(d.id, d.qty, d.dept, d.itemid);
            } else if (action === 'print-po') {
                triggerInlinePOPrint(d.id, d.name, d.code, d.qty);
            } else if (action === 'edit-employee') {
                openEditEmployeeModal(d.id, d.name, d.role, d.loc, d.contact);
            } else if (action === 'edit-user') {
                openEditUserModal(d.id, d.name, d.desig, d.loc, d.role);
            } else if (action === 'mis-dropdown-close') {
                document.getElementById('mis_item_dropdown').classList.add('hidden');
            }
        });

        // ---- MIS ITEM SEARCH ENGINE ----
        var MIS_INVENTORY_DATA = [];
        try { MIS_INVENTORY_DATA = JSON.parse(document.getElementById('mis-inventory-data').textContent); } catch(e) { MIS_INVENTORY_DATA = []; }

        function filterMISItems(query) {
            var dropdown = document.getElementById('mis_item_dropdown');
            if (!dropdown) return;
            if (!query || query.trim() === '') { dropdown.classList.add('hidden'); return; }
            var q = query.toLowerCase();
            var matches = MIS_INVENTORY_DATA.filter(function(i) {
                return i.name.toLowerCase().includes(q) || i.code.toLowerCase().includes(q);
            });
            if (matches.length === 0) {
                dropdown.innerHTML = '<div class="p-3 text-slate-400 text-xs">No matching items found</div>';
                dropdown.classList.remove('hidden');
                return;
            }
            dropdown.innerHTML = matches.slice(0, 10).map(function(i) {
                var stockColor = i.stock > 0 ? 'text-emerald-600' : 'text-rose-600';
                var safeName = i.name.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                var safeCode = i.code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                return '<div class="p-2.5 hover:bg-indigo-50 cursor-pointer border-b border-slate-100 last:border-0 mis-dropdown-item" data-id="' + i.id + '" data-name="' + safeName + '" data-code="' + safeCode + '" data-stock="' + i.stock + '">' +
                    '<div class="font-semibold text-slate-800 text-xs pointer-events-none">' + safeName + '</div>' +
                    '<div class="flex gap-2 mt-0.5 pointer-events-none"><span class="font-mono text-[10px] text-slate-400">' + safeCode + '</span><span class="text-[10px] font-bold ' + stockColor + '">Stock: ' + i.stock + '</span></div>' +
                    '</div>';
            }).join('');
            dropdown.classList.remove('hidden');
        }

        document.addEventListener('click', function(e) {
            var item = e.target.closest('.mis-dropdown-item');
            if (item) {
                selectMISItem(item.dataset.id, item.dataset.name, item.dataset.code, item.dataset.stock);
                return;
            }
            var dropdown = document.getElementById('mis_item_dropdown');
            var search = document.getElementById('mis_item_search');
            if (dropdown && search && !dropdown.contains(e.target) && e.target !== search) {
                dropdown.classList.add('hidden');
            }
        });

        function selectMISItem(id, name, code, stock) {
            document.getElementById('mis_item_id').value = id;
            document.getElementById('mis_item_search').value = name + ' (' + code + ')';
            document.getElementById('mis_item_dropdown').classList.add('hidden');
            var label = document.getElementById('mis_selected_item_label');
            label.textContent = 'Selected: ' + name + ' | Stock: ' + stock;
            label.classList.remove('hidden');
        }

        function showMISDropdown() {
            var val = document.getElementById('mis_item_search').value;
            if (val && val.trim().length > 0) filterMISItems(val);
        }
        // ---- END MIS ITEM SEARCH ----
        function switchTab(tabId) {
            // Hide all views cleanly
            document.getElementById('tab-viewport-inventory').style.display = 'none';
            document.getElementById('tab-viewport-requisitions').classList.add('hidden');
            document.getElementById('tab-viewport-requisitions').classList.remove('grid');
            document.getElementById('tab-viewport-allocations').classList.add('hidden');
            document.getElementById('tab-viewport-allocations').classList.remove('grid');

            // Reset navigation links styling
            const tabs = ['inventory', 'requisitions', 'allocations'];
            tabs.forEach(t => {
                const el = document.getElementById('nav-' + t);
                if (el) {
                    el.className = "w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all text-left group";
                    const icon = el.querySelector('i');
                    if (icon) icon.className = icon.className.replace('text-indigo-600', 'text-slate-400');
                }
            });

            // Activate chosen target viewport
            const activeNav = document.getElementById('nav-' + tabId);
            const breadcrumb = document.getElementById('header-breadcrumb');
            
            if (tabId === 'inventory') {
                document.getElementById('tab-viewport-inventory').style.display = 'grid';
                breadcrumb.innerText = "Inventory Status Dashboard";
                activeNav.className = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left";
                activeNav.querySelector('i').className = "fa-solid fa-boxes-stacked w-5 text-center text-indigo-600";
            } else if (tabId === 'requisitions') {
                document.getElementById('tab-viewport-requisitions').classList.remove('hidden');
                document.getElementById('tab-viewport-requisitions').classList.add('grid');
                breadcrumb.innerText = "Material Procurement Indents";
                activeNav.className = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left";
                activeNav.querySelector('i').className = "fa-solid fa-file-invoice-dollar w-5 text-center text-indigo-600";
            } else if (tabId === 'allocations') {
                document.getElementById('tab-viewport-allocations').classList.remove('hidden');
                document.getElementById('tab-viewport-allocations').classList.add('grid');
                breadcrumb.innerText = "Physical Asset Allocations & Issue Logs";
                activeNav.className = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left";
                activeNav.querySelector('i').className = "fa-solid fa-truck-ramp-box w-5 text-center text-indigo-600";
            }
            
            window.location.hash = tabId + "-panel";
        }

        window.addEventListener('DOMContentLoaded', () => {
            var urlParams = new URLSearchParams(window.location.search);
            var tabParam = urlParams.get('tab');
            if (tabParam === 'allocations' || window.location.hash.includes('allocations')) {
                switchTab('allocations');
            } else if (window.location.hash.includes('requisitions')) {
                switchTab('requisitions');
            } else {
                switchTab('inventory');
            }
        });

        function openEmployeeModal() { document.getElementById('employeeRegistrationModal').style.display = 'flex'; }
        function closeEmployeeModal() { document.getElementById('employeeRegistrationModal').style.display = 'none'; }
        
        function openAccessModal() { document.getElementById('grantAccessModal').style.display = 'flex'; }
        function closeAccessModal() { document.getElementById('grantAccessModal').style.display = 'none'; }

        function closeEditItemModal() { document.getElementById('editItemModal').style.display = 'none'; }
        function closeEditRequestModal() { document.getElementById('editRequestModal').style.display = 'none'; }

        function openEditItemModal(id, name, code, price, stock, minStock) {
    var modalHtml = `
        <h3 class="text-xs font-bold uppercase text-slate-900 tracking-wider border-b border-slate-100 pb-3">Modify Master Inventory Item</h3>
        <form action="/items/edit/${id}" method="POST" class="space-y-4 text-xs text-slate-700">
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Item Name</label>
                    <input type="text" name="name" value="${name}" required class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none">
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Unique Code</label>
                    <input type="text" name="item_code" value="${code}" readonly class="w-full bg-slate-100 border border-slate-200 p-2.5 rounded-xl text-slate-500 font-mono">
                </div>
            </div>
            <div class="grid grid-cols-3 gap-3">
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Price (₹)</label>
                    <input type="number" step="0.01" name="price" value="${price}" required class="w-full bg-slate-50 border p-2.5 rounded-xl font-mono">
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Stock Count</label>
                    <input type="number" name="current_stock" value="${stock}" required class="w-full bg-slate-50 border p-2.5 rounded-xl font-mono">
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Safety Min</label>
                    <input type="number" name="minimum_stock" value="${minStock}" required class="w-full bg-slate-50 border p-2.5 rounded-xl font-mono">
                </div>
            </div>
            <div class="flex gap-3 pt-2">
                <button type="button" onclick="closeEditItemModal()" class="w-1/2 bg-slate-100 text-slate-700 p-2.5 rounded-xl border">Cancel</button>
                <button type="submit" class="w-1/2 bg-indigo-600 text-white p-2.5 rounded-xl font-bold">Save Modifications</button>
            </div>
        </form>
    `;
    document.getElementById('editItemModalContent').innerHTML = modalHtml;
    document.getElementById('editItemModal').style.display = 'flex';
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

        function downloadTransactionCSVTemplate() {
            var csvContent = "item_code,type,quantity\\nEIPL-BM-01,IN,50\\nEIPL-WR-09,OUT,12";
            triggerCSVBlobDownload("EIPL_Transactions_Bulk_Template.csv", csvContent);
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
            var csvContent = "data:text/csv;charset=utf-8," + csv.join("\\n");
            var encodedUri = encodeURI(csvContent);
            var link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "EIPL_Master_Inventory_Report.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    </script>
</body>
</html>"""


# =========================================================================
# Place this at the very bottom of templates.py
# =========================================================================

PROCUREMENT_WIDGET_PANEL = """
<div class="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm space-y-4">
    <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
            <h3 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Create Procurement Indent</h3>
            <p class="text-[10px] text-slate-400 mt-0.5">Raise structural material indents pipeline queries</p>
        </div>
        <a href="/procurement/bulk-template" class="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 px-2.5 py-1.5 rounded-lg text-[10px] font-bold transition-all flex items-center gap-1 shadow-sm whitespace-nowrap">
            <i class="fa-solid fa-download"></i> Template
        </a>
    </div>
    
    <form action="/procurement/request" method="POST" class="space-y-4 text-xs text-slate-700 border-t border-slate-100 pt-3">
        <div>
            <label class="block font-semibold text-slate-600 mb-1.5">Select Inventory Stock Item</label>
            <select id="procurement_item_selector" name="item_id" onchange="toggleAdHocProcurementFields()" class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm font-medium">
                <option value="NEW_PROCUREMENT_AD_HOC" class="text-amber-600 font-bold font-mono">➕ ITEM NOT IN LIST (NEW PROCUREMENT REQUEST)</option>
                __OPTIONS__
            </select>
        </div>

        <div id="adhoc_procurement_fields_group" class="space-y-4 bg-amber-50/40 p-4 border border-amber-200/50 rounded-xl transition-all duration-300">
            <div>
                <label class="block font-bold text-amber-800 mb-1">New Item Name <span class="text-rose-500">*</span></label>
                <input type="text" id="new_item_name_input" name="new_item_name" placeholder="Enter custom item name description" class="w-full bg-white border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
            </div>
            <div>
                <label class="block font-bold text-amber-800 mb-1">Detailed Specification <span class="text-rose-500">*</span></label>
                <textarea id="detailed_specification_input" name="detailed_specification" rows="3" placeholder="Enter mandatory technical specifications, grade, measurements, size dimensions, or brand limits..." class="w-full bg-white border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm resize-none"></textarea>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
            <div>
                <label class="block font-semibold text-slate-600 mb-1.5">Quantity Required</label>
                <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm font-mono font-semibold">
            </div>
            <div>
                <label class="block font-semibold text-slate-600 mb-1.5">Department / Cost Center</label>
                <input type="text" name="department" placeholder="e.g. Udaipur Project" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
            </div>
        </div>

        <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all shadow-md shadow-indigo-600/10">
            Authorize Indent Workflow
        </button>
    </form>

    <div class="pt-3 border-t border-dashed border-slate-200">
        <label class="block font-black text-[10px] uppercase text-indigo-600 mb-2 tracking-wider flex items-center gap-1">📊 Bulk Indent Import (CSV)</label>
        <form action="/procurement/bulk-import" method="POST" enctype="multipart/form-data" class="flex gap-2">
            <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border border-slate-200 text-slate-600 text-[10px] p-2 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
            <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-2 rounded-xl font-bold text-[10px] tracking-wide transition-all shrink-0 shadow-sm">Import</button>
        </form>
        <p class="text-[10px] text-slate-400 mt-1">Download the template above to see the required CSV format.</p>
    </div>
</div>

<script>
    function toggleAdHocProcurementFields() {
        var selector = document.getElementById('procurement_item_selector');
        var fieldsBox = document.getElementById('adhoc_procurement_fields_group');
        var nameInput = document.getElementById('new_item_name_input');
        var specInput = document.getElementById('detailed_specification_input');
        
        if (!selector || !fieldsBox) return;

        if (selector.value === 'NEW_PROCUREMENT_AD_HOC') {
            fieldsBox.style.display = 'block';
            nameInput.required = true;
            specInput.required = true;
            nameInput.placeholder = "Enter custom item name description... (Required)";
            specInput.placeholder = "Enter mandatory dimensions, grade, or brand limits... (Required)";
        } else {
            fieldsBox.style.display = 'none';
            nameInput.required = false;
            specInput.required = false;
            nameInput.value = "";
            specInput.value = "";
        }
    }

    window.addEventListener('DOMContentLoaded', () => {
        setTimeout(toggleAdHocProcurementFields, 200);
    });
</script>
"""