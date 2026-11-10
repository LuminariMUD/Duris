const table = document.querySelector("#ival-table");
const body = table.tBodies[0];
const rows = [...body.rows];
const search = document.querySelector("#ival-search");
const status = document.querySelector("#ival-status");
const empty = document.querySelector("#ival-empty");
const filters = [...document.querySelectorAll("[data-direction]")];
let direction = "all";

function update() {
  const query = search.value.trim().toLowerCase();
  let shown = 0;
  for (const row of rows) {
    const up = Number(row.dataset.delta) > 0;
    const match =
      row.dataset.search.includes(query) &&
      (direction === "all" || up === (direction === "up"));
    row.hidden = !match;
    if (match) shown++;
  }
  status.textContent = `Showing ${shown} of ${rows.length} items.`;
  empty.hidden = shown > 0;
}

search.addEventListener("input", update);
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
