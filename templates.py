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
        <div class="p-5 border-b border-slate-100 text-center">
            <img src="/static/logo.png" alt="EIPL Logo"
                class="h-20 mx-auto mb-2 object-contain"
                onerror="this.style.display='none';document.getElementById('logoFallback').style.display='inline-block';">
            <div id="logoFallback" style="display:none;" class="bg-indigo-600 px-3 py-2 rounded-xl text-white shadow-md shadow-indigo-600/20 font-black tracking-tighter text-sm mb-2">
                EIPL
            </div>
            <h2 class="font-black text-slate-900 tracking-tight text-[13px] leading-tight uppercase">Electra Infracon Pvt Ltd</h2>
            <p class="text-[10px] text-slate-400 font-mono mt-1">UID: __USER__</p>
        </div>

        <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2 font-semibold">Core Dashboard</p>
            
            <a href="/material-movement" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all text-left group">
                <i class="fa-solid fa-truck-ramp-box w-5 text-center text-slate-400 group-hover:text-emerald-600"></i> Material Movement
            </a>

            <a href="/inventory/summary" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all text-left group">
                <i class="fa-solid fa-chart-bar w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Material Flow Dashboard
            </a>

            <button id="nav-inventory" onclick="switchTab('inventory')" class="w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left">
                <i class="fa-solid fa-boxes-stacked w-5 text-center text-indigo-600"></i> Inventory Configuration
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
                <span id="header-breadcrumb" class="text-slate-700 font-medium">Inventory Configuration Dashboard</span>
            </div>
        </header>

        <div class="flex-1 p-6 space-y-6 overflow-y-auto max-w-[1650px] w-full mx-auto">
            
            <div id="tab-viewport-inventory" class="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                
                <div class="xl:col-span-1 space-y-6">
                    __ADMIN_PANEL__
                </div>

                <div class="xl:col-span-2">
                    <div id="inventory-table-container" class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                        <div class="p-5 border-b border-slate-100 bg-white flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Consolidated Inventory Configuration</h2>
                                <p class="text-[10px] text-slate-400 mt-0.5">Real-time warehouse material mapping and safety levels</p>
                            </div>
                            <div class="flex flex-wrap items-center gap-2">
                                <div class="relative">
                                    <i class="fa-solid fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-[10px]"></i>
                                    <input type="text" id="invSearch" placeholder="Search inventory..." oninput="filterTable('inv')"
                                        class="pl-7 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-400 w-40">
                                </div>
                                <select id="invPageSize" onchange="changePageSize('inv')" class="bg-slate-50 border border-slate-200 text-xs px-2.5 py-2 rounded-xl focus:outline-none focus:border-indigo-400">
                                    <option value="15">15 / page</option>
                                    <option value="50">50 / page</option>
                                    <option value="100">100 / page</option>
                                </select>
                                <button onclick="downloadInventoryExcel()" class="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm">
                                    <i class="fa-solid fa-file-excel"></i> Export
                                </button>
                            </div>
                        </div>
                        <div class="overflow-x-auto">
                            <table id="inventoryTable" class="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase border-b border-slate-200">
                                        <th class="p-4 pl-5 cursor-pointer hover:text-indigo-600" onclick="sortTable('inv',0)">Item Name <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortTable('inv',1)">Item Code <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 admin-only-col cursor-pointer hover:text-indigo-600" onclick="sortTable('inv',2)">Vendor <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 admin-only-col cursor-pointer hover:text-indigo-600" onclick="sortTable('inv',3)">Price <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('inv',4)">Current Stock <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('inv',5)">Safety Stock <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 text-right pr-5">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="invTableBody" class="divide-y divide-slate-100 font-medium text-slate-700">
                                    __INVENTORY_ROWS__
                                </tbody>
                            </table>
                        </div>
                        <div id="invPaginationBar" class="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50/50 text-xs text-slate-500">
                            <span id="invPageInfo"></span>
                            <div class="flex items-center gap-1" id="invPageButtons"></div>
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

            <div id="tab-viewport-requisitions" class="hidden flex-col gap-6">

                <!-- CREATE PROCUREMENT INDENT: Landscape full-width card -->
                <div class="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
                    <div class="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                        <div>
                            <h3 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Create Procurement Indent</h3>
                            <p class="text-[10px] text-slate-400 mt-0.5">Raise structural material indents — fill all fields and authorize</p>
                        </div>
                        <div class="flex items-center gap-2">
                            <a href="/procurement/bulk-template" class="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 px-2.5 py-1.5 rounded-lg text-[10px] font-bold transition-all flex items-center gap-1 shadow-sm whitespace-nowrap">
                                <i class="fa-solid fa-download"></i> Template
                            </a>
                        </div>
                    </div>

                    <!-- Main form: landscape grid layout -->
                    <form action="/procurement/request" method="POST" class="text-xs text-slate-700">
                        <!-- Search & Select Item — MIS style, full width above grid -->
                        <div class="relative mb-3">
                            <label class="block font-semibold text-slate-600 mb-1.5">Search &amp; Select Stock Item</label>
                            <input type="text" id="proc_item_search" placeholder="Type item name or code — or select NEW below..." autocomplete="off"
                                class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm"
                                oninput="filterProcItems(this.value)" onfocus="showProcDropdown()">
                            <div id="proc_item_dropdown" class="absolute z-30 w-full bg-white border border-slate-200 rounded-xl shadow-xl mt-1 max-h-48 overflow-y-auto hidden"></div>
                            <input type="hidden" id="proc_item_id" name="item_id" value="NEW_PROCUREMENT_AD_HOC">
                            <p id="proc_selected_item_label" class="text-[10px] text-indigo-600 font-semibold mt-1"></p>
                        </div>
                        <div class="grid grid-cols-3 gap-3 mb-3">
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Quantity Required</label>
                                <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm font-mono font-semibold">
                            </div>
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Unit of Measure (UOM)</label>
                                <select name="uom" class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
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
                            <div>
                                <label class="block font-semibold text-slate-600 mb-1.5">Department / Cost Center</label>
                                <input type="text" name="department" placeholder="e.g. Udaipur Project" required class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 focus:bg-white shadow-sm">
                            </div>
                        </div>

                        <!-- Ad-hoc fields: shown only when NEW is selected -->
                        <div id="adhoc_procurement_fields_group" class="grid grid-cols-2 gap-3 mb-3 bg-amber-50/40 p-3 border border-amber-200/50 rounded-xl">
                            <div>
                                <label class="block font-bold text-amber-800 mb-1">New Item Name <span class="text-rose-500">*</span></label>
                                <input type="text" id="new_item_name_input" name="new_item_name" placeholder="Enter custom item name" class="w-full bg-white border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
                            </div>
                            <div>
                                <label class="block font-bold text-amber-800 mb-1">Detailed Specification <span class="text-rose-500">*</span></label>
                                <textarea id="detailed_specification_input" name="detailed_specification" rows="1" placeholder="Technical specs, grade, dimensions, brand limits..." class="w-full bg-white border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm resize-none"></textarea>
                            </div>
                        </div>

                        <div class="flex items-center gap-3">
                            <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 p-2.5 rounded-xl font-bold tracking-wide transition-all shadow-md shadow-indigo-600/10 text-xs">
                                Authorize Indent Workflow
                            </button>
                            <span class="text-[10px] text-slate-400">or use Bulk Import →</span>
                            <form action="/procurement/bulk-import" method="POST" enctype="multipart/form-data" class="flex gap-2 flex-1">
                                <input type="file" name="file" accept=".csv" required class="flex-1 bg-slate-50 border border-slate-200 text-slate-600 text-[10px] p-2 rounded-xl focus:outline-none focus:border-indigo-600 shadow-sm">
                                <button type="submit" class="bg-slate-700 hover:bg-slate-800 text-white px-3 py-2 rounded-xl font-bold text-[10px] tracking-wide transition-all shrink-0 shadow-sm">Import CSV</button>
                            </form>
                        </div>
                    </form>
                </div>

                <!-- PROCUREMENT PIPELINE TABLE: full-width with search + pagination -->
                <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                    <div class="p-5 border-b border-slate-100 bg-white">
                        <div class="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Procurement Pipeline Indents</h2>
                                <p class="text-[10px] text-slate-400 mt-0.5">Formal procurement intent registries and operations pipeline tracker</p>
                            </div>
                            <div class="flex flex-wrap items-center gap-2">
                                <!-- Search box -->
                                <div class="relative">
                                    <i class="fa-solid fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-[10px]"></i>
                                    <input type="text" id="reqSearch" placeholder="Search indents..." oninput="filterTable('req')"
                                        class="pl-7 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-400 w-44">
                                </div>
                                <!-- Status filter -->
                                <select id="reqStatusFilter" onchange="filterTable('req')" class="bg-slate-50 border border-slate-200 text-xs px-2.5 py-2 rounded-xl focus:outline-none focus:border-indigo-400">
                                    <option value="">All Statuses</option>
                                    <option value="Pending">Pending</option>
                                    <option value="Accepted">Accepted</option>
                                    <option value="Rejected">Rejected</option>
                                </select>
                                <!-- Per-page selector -->
                                <select id="reqPageSize" onchange="changePageSize('req')" class="bg-slate-50 border border-slate-200 text-xs px-2.5 py-2 rounded-xl focus:outline-none focus:border-indigo-400">
                                    <option value="15">15 / page</option>
                                    <option value="50">50 / page</option>
                                    <option value="100">100 / page</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table id="reqTable" class="w-full text-left border-collapse text-xs">
                            <thead>
                                <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase border-b border-slate-200">
                                    <th class="p-3 pl-5 whitespace-nowrap text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('req',0)">Time Stamp <i class="fa-solid fa-sort text-[9px]"></i></th>
                                    <th class="p-3 text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('req',1)">Item Description <i class="fa-solid fa-sort text-[9px]"></i></th>
                                    <th class="p-3 text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('req',2)">Qty <i class="fa-solid fa-sort text-[9px]"></i></th>
                                    __EST_VALUE_HEADER__
                                    <th class="p-3 text-center">Item Code</th>
                                    <th class="p-3 text-center">Specification</th>
                                    <th class="p-3 text-center whitespace-nowrap cursor-pointer hover:text-indigo-600" onclick="sortTable('req',6)">Requested By <i class="fa-solid fa-sort text-[9px]"></i></th>
                                    <th class="p-3 text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('req',7)">Status <i class="fa-solid fa-sort text-[9px]"></i></th>
                                    <th class="p-3 text-center">Communication</th>
                                    <th class="p-3 text-center whitespace-nowrap">Workflow</th>
                                </tr>
                            </thead>
                            <tbody id="reqTableBody" class="divide-y divide-slate-100 font-medium text-slate-700">
                                __REG_ROWS__
                            </tbody>
                        </table>
                    </div>
                    <!-- Pagination bar -->
                    <div id="reqPaginationBar" class="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50/50 text-xs text-slate-500">
                        <span id="reqPageInfo"></span>
                        <div class="flex items-center gap-1" id="reqPageButtons"></div>
                    </div>
                </div>
            </div>

            <div id="tab-viewport-allocations" class="hidden grid-cols-1 gap-6 items-start">
                
                <div class="xl:col-span-3">
                    <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                        <div class="p-5 border-b border-slate-100 bg-white">
                            <div class="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Physical Asset Allocations Journal</h2>
                                    <p class="text-[10px] text-slate-400 mt-0.5">Permanent deployment records and site field custodian mapping</p>
                                </div>
                                <div class="flex flex-wrap items-center gap-2">
                                    <div class="relative">
                                        <i class="fa-solid fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-[10px]"></i>
                                        <input type="text" id="allocSearch" placeholder="Search allocations..." oninput="filterTable('alloc')"
                                            class="pl-7 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-400 w-40">
                                    </div>
                                    <select id="allocPageSize" onchange="changePageSize('alloc')" class="bg-slate-50 border border-slate-200 text-xs px-2.5 py-2 rounded-xl focus:outline-none focus:border-indigo-400">
                                        <option value="15">15 / page</option>
                                        <option value="50">50 / page</option>
                                        <option value="100">100 / page</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        <div class="overflow-x-auto">
                            <table id="allocTable" class="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase border-b border-slate-200">
                                        <th class="p-4 pl-5 cursor-pointer hover:text-indigo-600" onclick="sortTable('alloc',0)">Date &amp; Time <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortTable('alloc',1)">Item Name <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 text-center cursor-pointer hover:text-indigo-600" onclick="sortTable('alloc',2)">Quantity <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 text-center">UOM</th>
                                        <th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortTable('alloc',4)">Issued To <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortTable('alloc',5)">Department <i class="fa-solid fa-sort text-[9px]"></i></th>
                                        <th class="p-4 pr-5">Remarks</th>
                                    </tr>
                                </thead>
                                <tbody id="allocTableBody" class="divide-y divide-slate-100 font-medium text-slate-700">
                                    __ASSIGNED_ROWS__
                                </tbody>
                            </table>
                        </div>
                        <div id="allocPaginationBar" class="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50/50 text-xs text-slate-500">
                            <span id="allocPageInfo"></span>
                            <div class="flex items-center gap-1" id="allocPageButtons"></div>
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

    <div id="editUserModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm items-center justify-center z-50 p-4" style="display:none;">
        <div id="editUserModalContent" class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl text-slate-800"></div>
    </div>

    <div id="editEmployeeModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm items-center justify-center z-50 p-4" style="display:none;">
        <div id="editEmployeeModalContent" class="bg-white border border-slate-200 p-6 rounded-2xl max-w-md w-full space-y-4 shadow-2xl text-slate-800"></div>
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
                openInwardFormForItem(d.id, d.name, d.code, d.price, d.uom, d.vendor);
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

        // ---- INWARD ITEM SEARCH ENGINE (unified Inward Transaction panel) ----
        function filterInwardItems(query) {
            var dropdown = document.getElementById('inward_item_dropdown');
            if (!dropdown) return;
            var newOpt = '<div class="p-2.5 hover:bg-amber-50 cursor-pointer border-b border-amber-100 inward-dropdown-item font-bold text-amber-700 text-xs" data-id="NEW_INWARD_ITEM" data-name="" data-code="" data-uom="" data-price="" data-vendor="">&#10133; NEW ITEM (Add to Catalog)</div>';
            if (!query || query.trim() === '') {
                dropdown.innerHTML = newOpt + '<div class="p-3 text-slate-400 text-xs">Type to search existing items...</div>';
                dropdown.classList.remove('hidden'); return;
            }
            var q = query.toLowerCase();
            var matches = MIS_INVENTORY_DATA.filter(function(i) {
                return i.name.toLowerCase().includes(q) || i.code.toLowerCase().includes(q);
            });
            var itemsHtml = matches.slice(0, 10).map(function(i) {
                var stockColor = i.stock > 0 ? 'text-emerald-600' : 'text-rose-600';
                var safeName = i.name.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                var safeCode = i.code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                var uomBadge = i.uom ? ' <span class="text-[9px] font-bold text-indigo-500 bg-indigo-50 px-1 rounded">🔒' + i.uom + '</span>' : '';
                return '<div class="p-2.5 hover:bg-indigo-50 cursor-pointer border-b border-slate-100 last:border-0 inward-dropdown-item" data-id="' + i.id + '" data-name="' + safeName + '" data-code="' + safeCode + '" data-uom="' + (i.uom||'') + '" data-price="' + (i.price||0) + '" data-vendor="' + (i.vendor||'').replace(/"/g,'&quot;') + '">' +
                    '<div class="font-semibold text-slate-800 text-xs pointer-events-none">' + safeName + uomBadge + '</div>' +
                    '<div class="flex gap-2 mt-0.5 pointer-events-none"><span class="font-mono text-[10px] text-slate-400">' + safeCode + '</span><span class="text-[10px] font-bold ' + stockColor + '">Stock: ' + i.stock + '</span></div>' +
                    '</div>';
            }).join('');
            dropdown.innerHTML = newOpt + (itemsHtml || '<div class="p-3 text-slate-400 text-xs">No matching items found</div>');
            dropdown.classList.remove('hidden');
        }
        function showInwardDropdown() { filterInwardItems(document.getElementById('inward_item_search').value || ''); }
        function selectInwardItem(id, name, code, uom, price, vendor) {
            var isNew = (id === 'NEW_INWARD_ITEM');
            document.getElementById('inward_item_id').value = id;
            document.getElementById('inward_item_search').value = isNew ? '' : name + ' (' + code + ')';
            document.getElementById('inward_item_dropdown').classList.add('hidden');
            var label = document.getElementById('inward_selected_label');
            var newFields = document.getElementById('inward_new_item_fields');
            var uomSelect = document.getElementById('inward_uom_select');
            var uomDisplay = document.getElementById('inward_uom_display');
            if (isNew) {
                label.textContent = '+ New item — fill item details below';
                label.className = 'text-[10px] text-amber-600 font-semibold mt-1';
                if (newFields) newFields.style.display = 'block';
                if (uomSelect) uomSelect.style.display = '';
                if (uomDisplay) uomDisplay.style.display = 'none';
                var nameIn = document.getElementById('inward_new_name');
                var codeIn = document.getElementById('inward_new_code');
                if (nameIn) { nameIn.required = true; }
                if (codeIn) { codeIn.required = true; }
            } else {
                label.textContent = 'Selected: ' + name + ' (' + code + ')';
                label.className = 'text-[10px] text-indigo-600 font-semibold mt-1';
                if (newFields) newFields.style.display = 'none';
                var nameIn = document.getElementById('inward_new_name');
                var codeIn = document.getElementById('inward_new_code');
                if (nameIn) { nameIn.required = false; nameIn.value = ''; }
                if (codeIn) { codeIn.required = false; codeIn.value = ''; }
                // Handle UOM lock
                if (uom) {
                    if (uomSelect) uomSelect.style.display = 'none';
                    if (uomDisplay) uomDisplay.style.display = 'block';
                    var lockedVal = document.getElementById('inward_uom_locked_val');
                    var lockedText = document.getElementById('inward_uom_locked_text');
                    if (lockedVal) lockedVal.value = uom;
                    if (lockedText) lockedText.textContent = uom;
                    if (uomSelect) uomSelect.removeAttribute('required');
                } else {
                    if (uomSelect) { uomSelect.style.display = ''; uomSelect.required = true; }
                    if (uomDisplay) uomDisplay.style.display = 'none';
                }
                // Pre-fill vendor and price (editable)
                var vendorIn = document.getElementById('inward_vendor');
                var priceIn = document.getElementById('inward_price');
                if (vendorIn && vendor) vendorIn.value = vendor;
                if (priceIn && price) priceIn.value = parseFloat(price).toFixed(2);
            }
        }
        document.addEventListener('click', function(e) {
            var item = e.target.closest('.inward-dropdown-item');
            if (item) { selectInwardItem(item.dataset.id, item.dataset.name, item.dataset.code, item.dataset.uom, item.dataset.price, item.dataset.vendor); return; }
            var dd = document.getElementById('inward_item_dropdown');
            var sr = document.getElementById('inward_item_search');
            if (dd && sr && !dd.contains(e.target) && e.target !== sr) dd.classList.add('hidden');
        });
        // Initialize inward form: default to NEW mode
        window.addEventListener('DOMContentLoaded', function() {
            var newFields = document.getElementById('inward_new_item_fields');
            if (newFields) newFields.style.display = 'block';
        });

        // Called when "⬇ Inward" button is clicked on any row
        function openInwardFormForItem(id, name, code, price, uom, vendor) {
            // Switch to inventory tab (it's already there in tab-viewport-inventory)
            // Pre-fill the inward form with this item
            var searchEl = document.getElementById('inward_item_search');
            if (searchEl) {
                searchEl.value = name + ' (' + code + ')';
            }
            selectInwardItem(id, name, code, uom, price, vendor);
            // Scroll inward form into view
            var form = document.getElementById('inwardForm');
            if (form) {
                form.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Brief highlight
                form.style.transition = 'box-shadow 0.3s';
                form.style.boxShadow = '0 0 0 3px #059669';
                setTimeout(function() { form.style.boxShadow = ''; }, 1500);
            }
        }
        // ---- END INWARD ITEM SEARCH ----

        // ---- PROC ITEM SEARCH ENGINE (Procurement Indent) ----
        function filterProcItems(query) {
            var dropdown = document.getElementById('proc_item_dropdown');
            if (!dropdown) return;
            // Always show NEW option at top
            var newOpt = '<div class="p-2.5 hover:bg-amber-50 cursor-pointer border-b border-amber-100 proc-dropdown-item font-bold text-amber-700 text-xs" data-id="NEW_PROCUREMENT_AD_HOC" data-name="NEW — Not in Catalog" data-code="" data-stock="">&#10133; NEW ITEM (Not in catalog)</div>';
            if (!query || query.trim() === '') {
                dropdown.innerHTML = newOpt + '<div class="p-3 text-slate-400 text-xs">Type to search catalog items...</div>';
                dropdown.classList.remove('hidden'); return;
            }
            var q = query.toLowerCase();
            var matches = MIS_INVENTORY_DATA.filter(function(i) {
                return i.name.toLowerCase().includes(q) || i.code.toLowerCase().includes(q);
            });
            var itemsHtml = matches.slice(0, 10).map(function(i) {
                var stockColor = i.stock > 0 ? 'text-emerald-600' : 'text-rose-600';
                var safeName = i.name.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                var safeCode = i.code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                return '<div class="p-2.5 hover:bg-indigo-50 cursor-pointer border-b border-slate-100 last:border-0 proc-dropdown-item" data-id="' + i.id + '" data-name="' + safeName + '" data-code="' + safeCode + '" data-stock="' + i.stock + '">' +
                    '<div class="font-semibold text-slate-800 text-xs pointer-events-none">' + safeName + '</div>' +
                    '<div class="flex gap-2 mt-0.5 pointer-events-none"><span class="font-mono text-[10px] text-slate-400">' + safeCode + '</span><span class="text-[10px] font-bold ' + stockColor + '">Stock: ' + i.stock + '</span></div>' +
                    '</div>';
            }).join('');
            dropdown.innerHTML = newOpt + (itemsHtml || '<div class="p-3 text-slate-400 text-xs">No matching items found</div>');
            dropdown.classList.remove('hidden');
        }
        function showProcDropdown() { filterProcItems(document.getElementById('proc_item_search').value); }
        function selectProcItem(id, name, code, stock) {
            document.getElementById('proc_item_id').value = id;
            var isNew = (id === 'NEW_PROCUREMENT_AD_HOC');
            document.getElementById('proc_item_search').value = isNew ? '' : name + ' (' + code + ')';
            document.getElementById('proc_item_dropdown').classList.add('hidden');
            var label = document.getElementById('proc_selected_item_label');
            if (isNew) {
                label.textContent = '+ New item — fill details below';
                label.className = 'text-[10px] text-amber-600 font-semibold mt-1';
            } else {
                label.textContent = 'Selected: ' + name + ' | Stock: ' + stock;
                label.className = 'text-[10px] text-indigo-600 font-semibold mt-1';
            }
            var adhoc = document.getElementById('adhoc_procurement_fields_group');
            if (adhoc) adhoc.style.display = isNew ? 'grid' : 'none';
        }
        document.addEventListener('click', function(e) {
            var item = e.target.closest('.proc-dropdown-item');
            if (item) { selectProcItem(item.dataset.id, item.dataset.name, item.dataset.code, item.dataset.stock); return; }
            var dd = document.getElementById('proc_item_dropdown');
            var sr = document.getElementById('proc_item_search');
            if (dd && sr && !dd.contains(e.target) && e.target !== sr) dd.classList.add('hidden');
        });
        // Initialize proc form state
        window.addEventListener('DOMContentLoaded', function() {
            var adhoc = document.getElementById('adhoc_procurement_fields_group');
            if (adhoc) adhoc.style.display = 'grid'; // default to NEW mode
            var label = document.getElementById('proc_selected_item_label');
            if (label) { label.textContent = '+ New item — fill details below or search above'; label.className = 'text-[10px] text-amber-600 font-semibold mt-1'; }
        });
        // ---- END PROC ITEM SEARCH ----

        // =====================================================================
        // UNIVERSAL SEARCH, SORT & PAGINATION ENGINE
        // =====================================================================
        var tableState = {
            inv:   { page: 1, pageSize: 15, sortCol: -1, sortDir: 1, filter: '', extraFilter: '' },
            req:   { page: 1, pageSize: 15, sortCol: -1, sortDir: 1, filter: '', extraFilter: '' },
            alloc: { page: 1, pageSize: 15, sortCol: -1, sortDir: 1, filter: '', extraFilter: '' }
        };

        var tableMap = {
            inv:   { bodyId: 'invTableBody',   infoId: 'invPageInfo',   btnsId: 'invPageButtons',   sizeId: 'invPageSize',   searchId: 'invSearch' },
            req:   { bodyId: 'reqTableBody',   infoId: 'reqPageInfo',   btnsId: 'reqPageButtons',   sizeId: 'reqPageSize',   searchId: 'reqSearch' },
            alloc: { bodyId: 'allocTableBody', infoId: 'allocPageInfo', btnsId: 'allocPageButtons', sizeId: 'allocPageSize', searchId: 'allocSearch' }
        };

        function getAllRows(key) {
            var tbody = document.getElementById(tableMap[key].bodyId);
            if (!tbody) return [];
            return Array.from(tbody.querySelectorAll('tr[data-row]'));
        }

        function filterTable(key) {
            var st = tableState[key];
            var searchEl = document.getElementById(tableMap[key].searchId);
            st.filter = searchEl ? searchEl.value.toLowerCase() : '';
            if (key === 'req') {
                var sf = document.getElementById('reqStatusFilter');
                st.extraFilter = sf ? sf.value.toLowerCase() : '';
            }
            st.page = 1;
            renderTable(key);
        }

        function changePageSize(key) {
            var sel = document.getElementById(tableMap[key].sizeId);
            tableState[key].pageSize = parseInt(sel.value);
            tableState[key].page = 1;
            renderTable(key);
        }

        function sortTable(key, col) {
            var st = tableState[key];
            if (st.sortCol === col) { st.sortDir *= -1; } else { st.sortCol = col; st.sortDir = 1; }
            st.page = 1;
            renderTable(key);
        }

        function getCellText(row, col) {
            var cells = row.querySelectorAll('td');
            if (!cells[col]) return '';
            return (cells[col].getAttribute('data-sort') || cells[col].innerText || '').trim().toLowerCase();
        }

        function renderTable(key) {
            var st = tableState[key];
            var allRows = getAllRows(key);

            // Filter
            var filtered = allRows.filter(function(row) {
                var text = row.getAttribute('data-text') || row.innerText.toLowerCase();
                var matchSearch = !st.filter || text.includes(st.filter);
                var matchExtra = true;
                if (key === 'req' && st.extraFilter) {
                    var statusCell = row.querySelector('td[data-status]');
                    matchExtra = statusCell ? statusCell.getAttribute('data-status').toLowerCase() === st.extraFilter : text.includes(st.extraFilter);
                }
                return matchSearch && matchExtra;
            });

            // Sort
            if (st.sortCol >= 0) {
                filtered.sort(function(a, b) {
                    var av = getCellText(a, st.sortCol), bv = getCellText(b, st.sortCol);
                    var an = parseFloat(av.replace(/[₹,]/g,'')), bn = parseFloat(bv.replace(/[₹,]/g,''));
                    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * st.sortDir;
                    return av.localeCompare(bv) * st.sortDir;
                });
            }

            // Paginate
            var total = filtered.length;
            var totalPages = Math.max(1, Math.ceil(total / st.pageSize));
            if (st.page > totalPages) st.page = totalPages;
            var start = (st.page - 1) * st.pageSize;
            var end = Math.min(start + st.pageSize, total);

            // Show/hide rows
            allRows.forEach(function(r) { r.style.display = 'none'; });
            filtered.slice(start, end).forEach(function(r) { r.style.display = ''; });

            // Info
            var infoEl = document.getElementById(tableMap[key].infoId);
            if (infoEl) infoEl.textContent = total === 0 ? 'No records found' : 'Showing ' + (start+1) + '–' + end + ' of ' + total + ' records';

            // Page buttons
            var btnsEl = document.getElementById(tableMap[key].btnsId);
            if (btnsEl) {
                var html = '';
                var btnBase = 'px-2.5 py-1 rounded-lg border text-[10px] font-semibold transition-all ';
                html += '<button onclick="goPage(\\''+key+'\\','+Math.max(1,st.page-1)+')" class="'+btnBase+'bg-white border-slate-200 hover:bg-indigo-50 text-slate-600">&laquo;</button>';
                var pStart = Math.max(1, st.page-2), pEnd = Math.min(totalPages, st.page+2);
                if (pStart > 1) html += '<button onclick="goPage(\\''+key+'\\',1)" class="'+btnBase+'bg-white border-slate-200 hover:bg-indigo-50 text-slate-600">1</button>';
                if (pStart > 2) html += '<span class="px-1 text-slate-400">…</span>';
                for (var p = pStart; p <= pEnd; p++) {
                    var active = p === st.page ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white border-slate-200 hover:bg-indigo-50 text-slate-600';
                    html += '<button onclick="goPage(\\''+key+'\\','+p+')" class="'+btnBase+active+'">'+p+'</button>';
                }
                if (pEnd < totalPages-1) html += '<span class="px-1 text-slate-400">…</span>';
                if (pEnd < totalPages) html += '<button onclick="goPage(\\''+key+'\\','+totalPages+')" class="'+btnBase+'bg-white border-slate-200 hover:bg-indigo-50 text-slate-600">'+totalPages+'</button>';
                html += '<button onclick="goPage(\\''+key+'\\','+Math.min(totalPages,st.page+1)+')" class="'+btnBase+'bg-white border-slate-200 hover:bg-indigo-50 text-slate-600">&raquo;</button>';
                btnsEl.innerHTML = html;
            }
        }

        function goPage(key, p) {
            tableState[key].page = p;
            renderTable(key);
        }

        // Tag all rows with data-row and data-text for engine to work
        function tagRows(bodyId) {
            var tbody = document.getElementById(bodyId);
            if (!tbody) return;
            tbody.querySelectorAll('tr').forEach(function(row) {
                row.setAttribute('data-row', '1');
                if (!row.getAttribute('data-text')) {
                    row.setAttribute('data-text', row.innerText.toLowerCase());
                }
            });
        }

        function switchTab(tabId) {
            document.getElementById('tab-viewport-inventory').style.display = 'none';
            var reqEl = document.getElementById('tab-viewport-requisitions');
            reqEl.classList.add('hidden'); reqEl.classList.remove('flex');
            var allocEl = document.getElementById('tab-viewport-allocations');
            allocEl.classList.add('hidden'); allocEl.classList.remove('grid');

            const tabs = ['inventory', 'requisitions', 'allocations'];
            tabs.forEach(t => {
                const el = document.getElementById('nav-' + t);
                if (el) {
                    el.className = "w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all text-left group";
                    const icon = el.querySelector('i');
                    if (icon) icon.className = icon.className.replace('text-indigo-600', 'text-slate-400');
                }
            });

            const activeNav = document.getElementById('nav-' + tabId);
            const breadcrumb = document.getElementById('header-breadcrumb');

            if (tabId === 'inventory') {
                document.getElementById('tab-viewport-inventory').style.display = 'grid';
                breadcrumb.innerText = "Inventory Configuration Dashboard";
                activeNav.className = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left";
                activeNav.querySelector('i').className = "fa-solid fa-boxes-stacked w-5 text-center text-indigo-600";
                tagRows('invTableBody'); renderTable('inv');
            } else if (tabId === 'requisitions') {
                reqEl.classList.remove('hidden'); reqEl.classList.add('flex');
                breadcrumb.innerText = "Material Procurement Indents";
                activeNav.className = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left";
                activeNav.querySelector('i').className = "fa-solid fa-file-invoice-dollar w-5 text-center text-indigo-600";
                tagRows('reqTableBody'); renderTable('req');
            } else if (tabId === 'allocations') {
                allocEl.classList.remove('hidden'); allocEl.classList.add('grid');
                breadcrumb.innerText = "Physical Asset Allocations & Issue Logs";
                activeNav.className = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl font-bold text-sm transition-all text-left";
                activeNav.querySelector('i').className = "fa-solid fa-truck-ramp-box w-5 text-center text-indigo-600";
                tagRows('allocTableBody'); renderTable('alloc');
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

            var openParam = urlParams.get('open');
            if (openParam === 'employee') {
                openEmployeeModal();
            } else if (openParam === 'access') {
                openAccessModal();
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
        <h3 class="text-xs font-bold uppercase text-slate-900 tracking-wider border-b border-slate-100 pb-3">&#9998; Modify Master Inventory Item</h3>
        <form action="/items/edit/${id}" method="POST" class="space-y-4 text-xs text-slate-700">
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Item Name</label>
                    <input type="text" name="name" value="${name}" required
                        class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                </div>
                <div>
                    <label class="block font-bold text-indigo-700 mb-1.5">&#9670; Unique Code <span class="text-rose-500">*</span></label>
                    <input type="text" name="item_code" value="${code}" required
                        class="w-full bg-white border-2 border-indigo-400 p-2.5 rounded-xl text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:ring-2 focus:ring-indigo-100 uppercase"
                        oninput="this.value=this.value.toUpperCase()"
                        placeholder="e.g. EIPL-ST-05">
                    <p class="text-[10px] text-indigo-500 mt-0.5 font-medium">&#9998; Click to edit — must be unique</p>
                </div>
            </div>
            <div class="grid grid-cols-3 gap-3">
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Price (&#8377;)</label>
                    <input type="number" step="0.01" name="price" value="${price}" required
                        class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl font-mono focus:outline-none focus:border-indigo-600 focus:bg-white">
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Stock Count</label>
                    <input type="number" name="current_stock" value="${stock}" required
                        class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl font-mono focus:outline-none focus:border-indigo-600 focus:bg-white">
                </div>
                <div>
                    <label class="block font-semibold text-slate-600 mb-1.5">Safety Min</label>
                    <input type="number" name="minimum_stock" value="${minStock}" required
                        class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl font-mono focus:outline-none focus:border-indigo-600 focus:bg-white">
                </div>
            </div>
            <div class="flex gap-3 pt-2 border-t border-slate-100">
                <button type="button" onclick="closeEditItemModal()"
                    class="w-1/2 bg-slate-100 hover:bg-slate-200 text-slate-700 p-2.5 rounded-xl border border-slate-200 font-bold transition-all">Cancel</button>
                <button type="submit"
                    class="w-1/2 bg-amber-500 hover:bg-amber-600 text-white p-2.5 rounded-xl font-bold transition-all shadow-md shadow-amber-500/20">&#10003; Save Changes</button>
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

        // ---- EDIT USER MODAL (Grant User Access panel) ----
        function openEditUserModal(id, fullName, designation, location, role) {
            var esc = function(s) { return (s||'').toString().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); };
            var modalHtml = `
                <h3 class="text-xs font-bold uppercase text-slate-900 tracking-wider border-b border-slate-100 pb-3">&#9998; Modify User Account</h3>
                <form action="/admin/users/edit/${id}" method="POST" class="space-y-4 text-xs text-slate-700">
                    <div>
                        <label class="block font-semibold text-slate-600 mb-1.5">Full Legal Name</label>
                        <input type="text" name="full_name" value="${esc(fullName)}" required
                            class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-600 mb-1.5">Designation</label>
                            <input type="text" name="designation" value="${esc(designation)}" required
                                class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-600 mb-1.5">Workstation Location</label>
                            <input type="text" name="workstation_location" value="${esc(location)}" required
                                class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                        </div>
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-600 mb-1.5">Access Role</label>
                        <select name="role" class="w-full bg-white font-bold border border-slate-200 p-2.5 rounded-xl focus:outline-none focus:border-indigo-600">
                            <option value="Staff" ${role === 'Staff' ? 'selected' : ''}>Staff Level</option>
                            <option value="Admin" ${role === 'Admin' ? 'selected' : ''}>Full Admin</option>
                        </select>
                    </div>
                    <div class="flex gap-3 pt-2 border-t border-slate-100">
                        <button type="button" onclick="closeEditUserModal()"
                            class="w-1/2 bg-slate-100 hover:bg-slate-200 text-slate-700 p-2.5 rounded-xl border border-slate-200 font-bold transition-all">Cancel</button>
                        <button type="submit"
                            class="w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-xl font-bold transition-all shadow-md">&#10003; Save Changes</button>
                    </div>
                </form>
            `;
            document.getElementById('editUserModalContent').innerHTML = modalHtml;
            document.getElementById('editUserModal').style.display = 'flex';
        }
        function closeEditUserModal() { document.getElementById('editUserModal').style.display = 'none'; }

        // ---- EDIT EMPLOYEE MODAL (Employee Registration panel) ----
        function openEditEmployeeModal(id, name, roleTitle, location, contact) {
            var esc = function(s) { return (s||'').toString().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); };
            var modalHtml = `
                <h3 class="text-xs font-bold uppercase text-slate-900 tracking-wider border-b border-slate-100 pb-3">&#9998; Modify Employee Record</h3>
                <form action="/employees/edit/${id}" method="POST" class="space-y-4 text-xs text-slate-700">
                    <div>
                        <label class="block font-semibold text-slate-600 mb-1.5">Employee Full Name</label>
                        <input type="text" name="name" value="${esc(name)}" required
                            class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-600 mb-1.5">Designation / Role</label>
                        <input type="text" name="role_title" value="${esc(roleTitle)}" required
                            class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-600 mb-1.5">Work Station Location</label>
                            <input type="text" name="location" value="${esc(location)}" required
                                class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-600 mb-1.5">Contact Mobile</label>
                            <input type="text" name="contact" value="${esc(contact)}" required
                                class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white">
                        </div>
                    </div>
                    <div class="flex gap-3 pt-2 border-t border-slate-100">
                        <button type="button" onclick="closeEditEmployeeModal()"
                            class="w-1/2 bg-slate-100 hover:bg-slate-200 text-slate-700 p-2.5 rounded-xl border border-slate-200 font-bold transition-all">Cancel</button>
                        <button type="submit"
                            class="w-1/2 bg-slate-800 hover:bg-slate-900 text-white p-2.5 rounded-xl font-bold transition-all shadow-md">&#10003; Save Changes</button>
                    </div>
                </form>
            `;
            document.getElementById('editEmployeeModalContent').innerHTML = modalHtml;
            document.getElementById('editEmployeeModal').style.display = 'flex';
        }
        function closeEditEmployeeModal() { document.getElementById('editEmployeeModal').style.display = 'none'; }

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
            // Build CSV matching exact table headers and data
            var isAdmin = __IS_ADMIN__;
            var headers = ['Item Name', 'Item Code'];
            if (isAdmin) { headers.push('Vendor / Supplier', 'Price (INR)'); }
            headers.push('Current Stock', 'Safety Stock');

            var rows = [headers];
            var tbody = document.getElementById('invTableBody');
            if (tbody) {
                tbody.querySelectorAll('tr[data-row]').forEach(function(row) {
                    var cells = row.querySelectorAll('td');
                    if (!cells.length) return;
                    var rowData = [];
                    // Item Name (strip LOW badge and category sub-text)
                    var nameCell = cells[0] ? cells[0].innerText.replace(/LOW/g,'').replace(/\\n/g,' ').trim() : '';
                    rowData.push(nameCell);
                    // Item Code
                    rowData.push(cells[1] ? cells[1].innerText.trim() : '');
                    if (isAdmin) {
                        // Vendor
                        rowData.push(cells[2] ? cells[2].innerText.trim() : '');
                        // Price — strip ₹ and commas
                        rowData.push(cells[3] ? cells[3].innerText.replace(/[₹,]/g,'').trim() : '');
                        // Current Stock
                        rowData.push(cells[4] ? cells[4].innerText.trim() : '');
                        // Safety Stock
                        rowData.push(cells[5] ? cells[5].innerText.trim() : '');
                    } else {
                        // Current Stock (col 2 for staff view)
                        rowData.push(cells[2] ? cells[2].innerText.trim() : '');
                        // Safety Stock
                        rowData.push(cells[3] ? cells[3].innerText.trim() : '');
                    }
                    rows.push(rowData);
                });
            }

            var csvContent = rows.map(function(r) {
                return r.map(function(cell) {
                    var val = (cell || '').toString().replace(/"/g, '""');
                    return '"' + val + '"';
                }).join(',');
            }).join('\\n');

            // Add BOM for Excel UTF-8 compatibility
            var BOM = '\\uFEFF';
            var blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' });
            var link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'EIPL_Consolidated_Inventory_' + new Date().toISOString().slice(0,10) + '.csv';
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