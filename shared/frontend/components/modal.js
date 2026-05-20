class ForgeModal extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: none; position: fixed; inset: 0; z-index: 1000; }
        :host([open]) { display: flex; align-items: center; justify-content: center; }
        .backdrop { position: absolute; inset: 0; background: rgba(0,0,0,.4); }
        .panel {
          position: relative; background: #fff; border-radius: var(--forge-radius, 8px);
          padding: 1.5rem; max-width: 500px; width: 90%; box-shadow: 0 4px 24px rgba(0,0,0,.15);
        }
        .close { position: absolute; top: .5rem; right: .5rem; background: none; border: none; font-size: 1.2rem; cursor: pointer; padding: .25rem .5rem; }
      </style>
      <div class="backdrop" data-action="close"></div>
      <div class="panel">
        <button class="close" data-action="close">&times;</button>
        <slot></slot>
      </div>
    `;
    this.shadowRoot.addEventListener("click", (e) => {
      if (e.target.dataset.action === "close") this.close();
    });
  }
  open() { this.setAttribute("open", ""); }
  close() { this.removeAttribute("open"); }
  static get observedAttributes() { return ["open"]; }
}
customElements.define("forge-modal", ForgeModal);
