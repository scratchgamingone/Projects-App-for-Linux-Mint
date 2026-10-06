"""
Custom GTK 3 CSS styles matching Linux Mint desktop aesthetics.
"""

from gi.repository import Gtk, Gdk

APP_CSS = b"""
/* Application Window Background */
window.app-window {
    background-color: #1e222b;
    color: #e2e8f0;
}

/* Header & Input Bar */
.search-card {
    background-color: #252b37;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 8px 12px;
}

.url-entry {
    background-color: #1a1e27;
    color: #f1f5f9;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}

.url-entry:focus {
    border-color: #10b981;
    box-shadow: 0 0 0 1px #10b981;
}

/* Repository Summary Header Card */
.repo-card {
    background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 4px 0px;
}

.repo-title {
    font-size: 18px;
    font-weight: 700;
    color: #f9fafb;
}

.repo-owner {
    font-size: 14px;
    color: #9ca3af;
}

.repo-desc {
    font-size: 13px;
    color: #d1d5db;
    margin-top: 4px;
}

/* Metadata Badge Pills */
.badge-pill {
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}

.badge-star {
    background-color: #78350f;
    color: #fef08a;
    border: 1px solid #b45309;
}

.badge-fork {
    background-color: #1e3a5f;
    color: #93c5fd;
    border: 1px solid #2563eb;
}

.badge-lang {
    background-color: #064e3b;
    color: #a7f3d0;
    border: 1px solid #059669;
}

.badge-license {
    background-color: #312e81;
    color: #c7d2fe;
    border: 1px solid #4f46e5;
}

.badge-branch {
    background-color: #374151;
    color: #e5e7eb;
    border: 1px solid #4b5563;
}

/* Big Install Action Button */
.btn-install {
    background: linear-gradient(180deg, #10b981 0%, #059669 100%);
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    border-radius: 6px;
    border: 1px solid #047857;
    padding: 8px 18px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.btn-install:hover {
    background: linear-gradient(180deg, #34d399 0%, #10b981 100%);
}

.btn-install:active {
    background: #047857;
}

/* Action Buttons */
.btn-action {
    background-color: #374151;
    color: #f3f4f6;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

.btn-action:hover {
    background-color: #4b5563;
    color: #ffffff;
}

/* Success Banner */
.banner-success {
    background-color: #064e3b;
    border: 1px solid #10b981;
    border-radius: 6px;
    padding: 10px 14px;
    color: #ecfdf5;
}

/* File Tree Styling */
.file-tree {
    background-color: #171b24;
    color: #d1d5db;
    border-right: 1px solid #2d3748;
}

.file-tree:selected {
    background-color: #065f46;
    color: #ffffff;
}

/* Code Breadcrumbs Bar */
.code-header-bar {
    background-color: #181d28;
    border-bottom: 1px solid #2d3748;
    padding: 6px 12px;
    font-size: 12px;
}

/* Notebook Tabs */
notebook tab {
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
}

notebook tab:checked {
    border-bottom: 2px solid #10b981;
    color: #10b981;
}
"""


def apply_custom_styles():
    """Loads and applies custom CSS to the active screen."""
    provider = Gtk.CssProvider()
    provider.load_from_data(APP_CSS)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
