/**
 * InvoicePro – Invoice Form JS
 * Handles multi-item rows, live GST calculation, product autocomplete
 */

(() => {
    // ── State ─────────────────────────────────────────────────────────
    let products = [];
    let rowCounter = 0;

    // ── Fetch product catalog ──────────────────────────────────────────
    async function loadProducts() {
        try {
            const res = await fetch('/invoices/api/products');
            products = await res.json();
        } catch (e) { products = []; }
    }

    // ── Helpers ────────────────────────────────────────────────────────
    const q  = v => parseFloat(v) || 0;
    const fmt = v => v.toFixed(2);

    function getTransactionType() {
        const el = document.getElementById('transaction_type');
        return el ? el.value : 'intra';
    }

    function calcRow(unitPrice, qty, discount, gstRate, txType) {
        const subtotal      = unitPrice * qty;
        const taxable       = Math.max(subtotal - discount, 0);
        const totalGst      = taxable * (gstRate / 100);
        const cgst          = txType === 'intra' ? totalGst / 2 : 0;
        const sgst          = txType === 'intra' ? totalGst / 2 : 0;
        const igst          = txType === 'inter' ? totalGst : 0;
        const lineTotal     = taxable + totalGst;
        return { subtotal, taxable, cgst, sgst, igst, totalGst, lineTotal };
    }

    // ── Recalculate all totals ─────────────────────────────────────────
    function recalcAll() {
        const txType = getTransactionType();
        let totSubtotal = 0, totDiscount = 0, totTaxable = 0;
        let totCgst = 0, totSgst = 0, totIgst = 0, totTotal = 0;

        document.querySelectorAll('.item-row').forEach(row => {
            const price    = q(row.querySelector('[data-field="unit_price"]')?.value);
            const qty      = q(row.querySelector('[data-field="quantity"]')?.value);
            const disc     = q(row.querySelector('[data-field="discount"]')?.value);
            const gstRate  = q(row.querySelector('[data-field="gst_rate"]')?.value);
            const c = calcRow(price, qty, disc, gstRate, txType);

            totSubtotal += c.subtotal;
            totDiscount += disc;
            totTaxable  += c.taxable;
            totCgst     += c.cgst;
            totSgst     += c.sgst;
            totIgst     += c.igst;
            totTotal    += c.lineTotal;

            const lineTotalEl = row.querySelector('[data-field="line_total"]');
            if (lineTotalEl) lineTotalEl.textContent = fmt(c.lineTotal);
        });

        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = fmt(val); };
        set('tot-subtotal',  totSubtotal);
        set('tot-discount',  totDiscount);
        set('tot-taxable',   totTaxable);
        set('tot-cgst',      totCgst);
        set('tot-sgst',      totSgst);
        set('tot-igst',      totIgst);
        set('tot-total',     totTotal);

        // Show/hide GST rows based on txType
        const intraRows = document.querySelectorAll('.gst-row-intra');
        const interRows = document.querySelectorAll('.gst-row-inter');
        intraRows.forEach(r => r.style.display = txType === 'intra' ? '' : 'none');
        interRows.forEach(r => r.style.display = txType === 'inter' ? '' : 'none');

        updateHiddenJson();
    }

    // ── Serialize items to hidden field ────────────────────────────────
    function updateHiddenJson() {
        const rows = [];
        document.querySelectorAll('.item-row').forEach(row => {
            rows.push({
                item_name:   row.querySelector('[data-field="item_name"]')?.value   || '',
                description: row.querySelector('[data-field="description"]')?.value || '',
                hsn_sac:     row.querySelector('[data-field="hsn_sac"]')?.value     || '',
                product_id:  row.querySelector('[data-field="product_id"]')?.value  || null,
                unit_price:  q(row.querySelector('[data-field="unit_price"]')?.value),
                quantity:    q(row.querySelector('[data-field="quantity"]')?.value),
                discount:    q(row.querySelector('[data-field="discount"]')?.value),
                gst_rate:    q(row.querySelector('[data-field="gst_rate"]')?.value),
            });
        });
        const h = document.getElementById('items_json');
        if (h) h.value = JSON.stringify(rows);
    }

    // ── Build a product <option> list ─────────────────────────────────
    function buildProductSelect(selected = null) {
        const opts = ['<option value="">— Select product —</option>'];
        products.forEach(p => {
            const sel = selected && selected == p.id ? ' selected' : '';
            opts.push(`<option value="${p.id}"${sel}>${p.name} (${p.unit})</option>`);
        });
        return opts.join('');
    }

    // ── Attach events to a row ─────────────────────────────────────────
    function attachRowEvents(row) {
        // Product select → auto-fill fields
        const productSelect = row.querySelector('[data-field="product_id"]');
        if (productSelect) {
            productSelect.addEventListener('change', () => {
                const p = products.find(x => x.id == productSelect.value);
                if (!p) return;
                const set = (f, v) => { const el = row.querySelector(`[data-field="${f}"]`); if (el) el.value = v; };
                set('item_name',  p.name);
                set('description',p.description);
                set('hsn_sac',    p.hsn_sac);
                set('unit_price', p.price);
                set('gst_rate',   p.gst_rate);
                recalcAll();
            });
        }

        // Number inputs → recalc
        row.querySelectorAll('input[type="number"], select').forEach(el => {
            el.addEventListener('input', recalcAll);
            el.addEventListener('change', recalcAll);
        });
        row.querySelectorAll('input[type="text"], textarea').forEach(el => {
            el.addEventListener('input', updateHiddenJson);
        });

        // Remove row
        row.querySelector('.remove-row')?.addEventListener('click', () => {
            if (document.querySelectorAll('.item-row').length > 1) {
                row.remove();
                recalcAll();
            }
        });
    }

    // ── Render a row ───────────────────────────────────────────────────
    function renderRow(data = {}) {
        rowCounter++;
        const id = `row-${rowCounter}`;
        const div = document.createElement('tr');
        div.className = 'item-row';
        div.dataset.id = id;
        div.innerHTML = `
          <td>
            <select data-field="product_id" style="min-width:140px">
              ${buildProductSelect(data.product_id)}
            </select>
          </td>
          <td><input type="text" data-field="item_name" value="${data.item_name || ''}" placeholder="Item name" required style="min-width:120px"></td>
          <td><input type="text" data-field="description" value="${data.description || ''}" placeholder="Description" style="min-width:100px"></td>
          <td><input type="text" data-field="hsn_sac" value="${data.hsn_sac || ''}" placeholder="HSN/SAC" style="width:90px"></td>
          <td><input type="number" data-field="quantity" value="${data.quantity ?? 1}" min="0.01" step="0.01" style="width:80px"></td>
          <td><input type="number" data-field="unit_price" value="${data.unit_price ?? 0}" min="0" step="0.01" style="width:100px"></td>
          <td><input type="number" data-field="discount" value="${data.discount ?? 0}" min="0" step="0.01" style="width:90px"></td>
          <td>
            <select data-field="gst_rate" style="width:90px">
              <option value="0"  ${data.gst_rate == 0   ? 'selected':''}>0%</option>
              <option value="5"  ${data.gst_rate == 5   ? 'selected':''}>5%</option>
              <option value="12" ${data.gst_rate == 12  ? 'selected':''}>12%</option>
              <option value="18" ${data.gst_rate == 18  ? 'selected':''}>18%</option>
              <option value="28" ${data.gst_rate == 28  ? 'selected':''}>28%</option>
            </select>
          </td>
          <td class="item-total"><span data-field="line_total">0.00</span></td>
          <td><button type="button" class="remove-row" title="Remove row">×</button></td>
        `;
        return div;
    }

    // ── Init ───────────────────────────────────────────────────────────
    async function init() {
        const tbody = document.getElementById('items-tbody');
        const addBtn = document.getElementById('add-item-btn');
        const txTypeEl = document.getElementById('transaction_type');

        if (!tbody) return;

        await loadProducts();

        // Pre-populate existing items (edit mode)
        const existingJson = document.getElementById('existing-items-json');
        const initialItems = existingJson ? JSON.parse(existingJson.value || '[]') : [];

        if (initialItems.length > 0) {
            initialItems.forEach(item => {
                const row = renderRow(item);
                tbody.appendChild(row);
                attachRowEvents(row);
            });
        } else {
            const row = renderRow();
            tbody.appendChild(row);
            attachRowEvents(row);
        }

        recalcAll();

        addBtn?.addEventListener('click', () => {
            const row = renderRow();
            tbody.appendChild(row);
            attachRowEvents(row);
            recalcAll();
        });

        txTypeEl?.addEventListener('change', recalcAll);

        // Validate before submit
        const form = document.getElementById('invoice-form');
        form?.addEventListener('submit', (e) => {
            const rows = document.querySelectorAll('.item-row');
            if (rows.length === 0) {
                e.preventDefault();
                alert('Please add at least one item.');
                return;
            }
            updateHiddenJson();
        });
    }

    document.addEventListener('DOMContentLoaded', init);
})();
