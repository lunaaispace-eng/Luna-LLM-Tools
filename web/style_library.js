// Luna-StylePrompt — cascading dropdowns + live search + preview + theming.
//
// Wires Category -> Subcategory -> Style so each narrows the next, searches across
// the library, shows the selected style's text in a read-only preview box, and gives
// the node a distinct colour. The `style` widget stays the source of truth.

import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";
import { ComfyWidgets } from "/scripts/widgets.js";

const NODE = "Luna-StylePrompt";
let DATA = null;                 // { categories, tree, all }
const contentCache = {};         // label -> content text

async function loadData() {
    if (DATA) return DATA;
    try {
        const res = await api.fetchApi("/style_prompt_library/tree");
        DATA = await res.json();
    } catch (e) {
        console.warn("[Luna-StylePrompt] tree fetch failed; using flat list.", e);
        DATA = null;
    }
    return DATA;
}

async function fetchContent(label) {
    if (!label) return "";
    if (label in contentCache) return contentCache[label];
    try {
        const res = await api.fetchApi("/style_prompt_library/content?label=" + encodeURIComponent(label));
        const j = await res.json();
        contentCache[label] = j.content || "";
    } catch (e) {
        contentCache[label] = "";
    }
    return contentCache[label];
}

const widgetOf = (node, name) => node.widgets?.find((w) => w.name === name);

function setOptions(widget, values, preferred) {
    if (!widget) return;
    widget.options.values = values;
    if (preferred && values.includes(preferred)) widget.value = preferred;
    else if (!values.includes(widget.value)) widget.value = values[0];
}

function labelsFor(category, subcategory) {
    if (!DATA) return null;
    if (category === "All") return DATA.all.slice();
    const subs = DATA.tree[category] || {};
    if (subcategory && subcategory !== "All") return (subs[subcategory] || []).slice();
    return Object.values(subs).flat().sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
}

function subcatsFor(category) {
    if (!DATA || category === "All") return ["All"];
    return ["All", ...Object.keys(DATA.tree[category] || {})];
}

function refreshStyleList(node) {
    const cat = widgetOf(node, "category");
    const sub = widgetOf(node, "subcategory");
    const style = widgetOf(node, "style");
    const search = widgetOf(node, "search");
    if (!style || !DATA) return;

    let labels = labelsFor(cat?.value, sub?.value) || DATA.all.slice();
    const q = (search?.value || "").trim().toLowerCase();
    if (q) {
        labels = DATA.all.filter((l) => l.toLowerCase().includes(q));
        if (labels.length === 0) labels = ["(no match)"];
    }
    setOptions(style, labels, style.value);
    node._splUpdatePreview?.();
    node.setDirtyCanvas(true, true);
}

// Read-only preview box showing the selected style's text.
function addPreview(node) {
    if (node._splPreview) return;
    const w = ComfyWidgets["STRING"](node, "stylepreview", ["STRING", { multiline: true }], app).widget;
    w.serializeValue = async () => "";   // don't bloat the saved workflow
    const el = w.inputEl;
    if (el) {
        el.readOnly = true;
        el.placeholder = "Select a style to preview its description…";
        el.style.opacity = "0.92";
        el.style.fontSize = "11px";
        el.style.fontFamily = "ui-monospace, Consolas, monospace";
        el.style.background = "#1b1622";
        el.style.color = "#d8cfe6";
        el.style.border = "1px solid #3a2f4a";
    }
    node._splPreview = w;
    node._splUpdatePreview = async () => {
        const style = widgetOf(node, "style");
        w.value = await fetchContent(style?.value || "");
    };
}

function styleNode(node) {
    node.color = "#4a2c6d";    // deep purple title bar
    node.bgcolor = "#241d2e";  // dark slate-purple body
    if (node.size[0] < 400) node.setSize([400, node.size[1]]);
}

function wire(node) {
    if (node._splWired) return;
    node._splWired = true;

    styleNode(node);
    addPreview(node);

    const cat = widgetOf(node, "category");
    const sub = widgetOf(node, "subcategory");
    const search = widgetOf(node, "search");
    const style = widgetOf(node, "style");

    const chain = (widget, fn) => {
        if (!widget) return;
        const orig = widget.callback;
        widget.callback = function () {
            const r = orig ? orig.apply(this, arguments) : undefined;
            try { fn(); } catch (e) { console.warn("[Luna-StylePrompt]", e); }
            return r;
        };
    };

    chain(cat, () => {
        setOptions(sub, subcatsFor(cat.value), "All");
        sub.value = "All";
        refreshStyleList(node);
    });
    chain(sub, () => refreshStyleList(node));
    chain(search, () => refreshStyleList(node));
    chain(style, () => node._splUpdatePreview?.());

    if (cat) setOptions(sub, subcatsFor(cat.value), sub?.value);
    refreshStyleList(node);
    node._splUpdatePreview?.();
}

app.registerExtension({
    name: "Luna-StylePrompt.CascadingMenu",
    async setup() { await loadData(); },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE) return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onCreated?.apply(this, arguments);
            const node = this;
            (async () => { await loadData(); wire(node); })();
            return r;
        };
    },
});
