const table = document.querySelector("#ival-table");
const body = table.tBodies[0];
const rows = [...body.rows];
const search = document.querySelector("#ival-search");
const status = document.querySelector("#ival-status");
const empty = document.querySelector("#ival-empty");
const stat = document.querySelector("#ival-stat");
const level = document.querySelector("#ival-level");
const type = document.querySelector("#ival-type");
const filters = [...document.querySelectorAll("[data-direction]")];
for (const row of rows) row.stats = JSON.parse(row.dataset.stats);
let direction = "all";

function update() {
  const query = search.value.trim().toLowerCase();
  let shown = 0;
  for (const row of rows) {
    const up = Number(row.dataset.delta) > 0;
    const match =
      row.dataset.search.includes(query) &&
      (!stat.value || stat.value in row.stats) &&
      (!level.value || Number(row.dataset.level) <= Number(level.value)) &&
      (!type.value || row.dataset.type === type.value) &&
      (direction === "all" || up === (direction === "up"));
    row.hidden = !match;
    if (match) shown++;
  }
  status.textContent = `Showing ${shown} of ${rows.length} items.`;
  empty.hidden = shown > 0;
}

for (const control of [search, level, type])
  control.addEventListener("input", update);
// Choosing a stat also ranks the matches by how much of it they give.
stat.addEventListener("input", () => {
  if (stat.value) {
    for (const heading of headings) heading.removeAttribute("aria-sort");
    rows.sort(
      (a, b) => (b.stats[stat.value] ?? 0) - (a.stats[stat.value] ?? 0),
    );
    body.append(...rows);
  }
  update();
});
for (const button of filters)
  button.addEventListener("click", () => {
    direction = button.dataset.direction;
    for (const other of filters)
      other.setAttribute("aria-pressed", String(other === button));
    update();
  });

const headings = [...table.querySelectorAll("th[data-sort]")];
for (const heading of headings) {
  const key = heading.dataset.sort;
  const text = key === "name" || key === "zone";
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = heading.textContent;
  heading.replaceChildren(button);
  button.addEventListener("click", () => {
    // Words start A to Z; numbers start with the largest.
    const first = text ? "ascending" : "descending";
    const order =
      heading.getAttribute("aria-sort") === first
        ? text
          ? "descending"
          : "ascending"
        : first;
    for (const other of headings) other.removeAttribute("aria-sort");
    heading.setAttribute("aria-sort", order);
    const sign = order === "ascending" ? 1 : -1;
    rows.sort((a, b) =>
      text
        ? sign * a.dataset[key].localeCompare(b.dataset[key])
        : sign * (a.dataset[key] - b.dataset[key]),
    );
    body.append(...rows);
  });
}

document.querySelector(".ival-controls").hidden = false;
