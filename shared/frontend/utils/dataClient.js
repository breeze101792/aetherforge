class DataClient {
  constructor(gatewayUrl = "http://127.0.0.1:8000") {
    this.base = gatewayUrl.replace(/\/$/, "");
    this.namespace = "__unknown__";
  }
  async create(resource, data) {
    const r = await fetch(`${this.base}/_api/data/${this.namespace}/${resource}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
    });
    if (!r.ok) throw new Error(`create failed: ${r.status}`);
    return r.json();
  }
  async list(resource, { limit = 100, offset = 0 } = {}) {
    const r = await fetch(`${this.base}/_api/data/${this.namespace}/${resource}?limit=${limit}&offset=${offset}`);
    if (!r.ok) throw new Error(`list failed: ${r.status}`);
    return r.json();
  }
  async get(resource, id) {
    const r = await fetch(`${this.base}/_api/data/${this.namespace}/${resource}/${id}`);
    if (!r.ok) throw new Error(`get failed: ${r.status}`);
    return r.json();
  }
  async update(resource, id, data) {
    const r = await fetch(`${this.base}/_api/data/${this.namespace}/${resource}/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
    });
    if (!r.ok) throw new Error(`update failed: ${r.status}`);
    return r.json();
  }
  async delete(resource, id) {
    const r = await fetch(`${this.base}/_api/data/${this.namespace}/${resource}/${id}`, {
      method: "DELETE"
    });
    if (!r.ok) throw new Error(`delete failed: ${r.status}`);
    return r.json();
  }
}
