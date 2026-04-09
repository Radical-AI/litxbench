// Heatmap coloring and click-to-sort for the benchmark leaderboard table.
(function () {
  "use strict";

  // Color stops: dark slate (0) -> teal (0.5) -> bright green (1)
  var LOW = [26, 26, 46];       // dark slate/grey (worst)
  var MID = [0, 120, 130];      // teal (middle)
  var HIGH = [0, 230, 120];     // bright green (best)
  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function heatmapRGB(normalized) {
    var t = Math.max(0, Math.min(1, normalized));
    var from, to, localT;
    if (t < 0.5) {
      from = LOW;
      to = MID;
      localT = t * 2;
    } else {
      from = MID;
      to = HIGH;
      localT = (t - 0.5) * 2;
    }
    return [
      Math.round(lerp(from[0], to[0], localT)),
      Math.round(lerp(from[1], to[1], localT)),
      Math.round(lerp(from[2], to[2], localT))
    ];
  }

  // Relative luminance (WCAG formula)
  function luminance(r, g, b) {
    var rs = r / 255, gs = g / 255, bs = b / 255;
    rs = rs <= 0.03928 ? rs / 12.92 : Math.pow((rs + 0.055) / 1.055, 2.4);
    gs = gs <= 0.03928 ? gs / 12.92 : Math.pow((gs + 0.055) / 1.055, 2.4);
    bs = bs <= 0.03928 ? bs / 12.92 : Math.pow((bs + 0.055) / 1.055, 2.4);
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
  }

  function parseCell(td) {
    // Extract numeric value, handling "0.72 ± 0.04" and "—"
    var text = td.textContent.trim();
    if (text === "\u2014" || text === "—" || text === "" || text === "-") return null;
    var num = parseFloat(text);
    return isNaN(num) ? null : num;
  }

  function applyHeatmap(table) {
    var headerRow = table.querySelectorAll("thead tr:last-child th");
    var rows = table.querySelectorAll("tbody tr");
    if (!rows.length) return;

    // For each numeric column, compute min/max then color cells.
    // headerRow only contains the 9 data headers (Prec..Cost) because
    // "Method" uses rowspan=2 and doesn't appear in the second <tr>.
    // But tbody rows have 10 <td> children starting with Method at index 0,
    // so the data cell index is col + 1.
    for (var col = 0; col < headerRow.length; col++) {
      var th = headerRow[col];
      var sortDir = th.getAttribute("data-sort");
      if (!sortDir) continue;
      var dataCol = col + 1; // offset for the Method <td>

      // Gather max for "lower" columns
      var colMax = 0;
      if (sortDir === "lower") {
        for (var r = 0; r < rows.length; r++) {
          var cell = rows[r].children[dataCol];
          if (!cell) continue;
          var val = parseCell(cell);
          if (val !== null && val > colMax) colMax = val;
        }
      }

      // Apply colors using absolute scales:
      // "higher" columns (scores 0-1): value IS the normalized score
      // "lower" columns (attempts/cost): 0 = bright, max in data = dark
      for (var r2 = 0; r2 < rows.length; r2++) {
        var cell2 = rows[r2].children[dataCol];
        if (!cell2) continue;
        var val2 = parseCell(cell2);
        if (val2 === null) {
          cell2.style.backgroundColor = "";
          cell2.style.color = "";
          continue;
        }
        var normalized;
        if (sortDir === "higher") {
          normalized = val2; // scores are 0-1, use directly
        } else {
          normalized = colMax > 0 ? 1 - val2 / colMax : 1;
        }
        var rgb = heatmapRGB(normalized);
        cell2.style.backgroundColor = "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
        // Use dark text on bright backgrounds, white text on dark ones
        var lum = luminance(rgb[0], rgb[1], rgb[2]);
        cell2.style.color = lum > 0.4 ? "#1a1a1a" : "#ffffff";
      }
    }
  }

  function initSort(table) {
    var headerRow = table.querySelectorAll("thead tr:last-child th");
    var tbody = table.querySelector("tbody");
    var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
    // Store original order
    var originalOrder = rows.slice();

    var currentSortCol = -1;
    var sortState = 0; // 0 = not sorted, 1 = primary, 2 = reversed

    for (var i = 0; i < headerRow.length; i++) {
      var th = headerRow[i];
      if (!th.getAttribute("data-sort")) continue;
      th.style.cursor = "pointer";
      th.addEventListener("click", (function (colIndex, thEl) {
        return function () {
          if (currentSortCol === colIndex) {
            sortState = (sortState + 1) % 3;
          } else {
            currentSortCol = colIndex;
            sortState = 1;
          }

          // Clear all sort indicators
          for (var j = 0; j < headerRow.length; j++) {
            var indicator = headerRow[j].querySelector(".sort-indicator");
            if (indicator) indicator.textContent = "";
          }

          if (sortState === 0) {
            // Restore original order
            for (var k = 0; k < originalOrder.length; k++) {
              tbody.appendChild(originalOrder[k]);
            }
            currentSortCol = -1;
          } else {
            var sortDir = thEl.getAttribute("data-sort");
            // sortState 1: best first (desc for higher, asc for lower)
            // sortState 2: reverse
            var ascending;
            if (sortState === 1) {
              ascending = (sortDir === "lower");
            } else {
              ascending = (sortDir !== "lower");
            }

            // Stable sort
            var indexed = rows.map(function (row, idx) {
              return { row: row, idx: idx, val: parseCell(row.children[colIndex + 1]) };
            });
            indexed.sort(function (a, b) {
              if (a.val === null && b.val === null) return a.idx - b.idx;
              if (a.val === null) return 1;
              if (b.val === null) return -1;
              var cmp = a.val - b.val;
              if (cmp === 0) return a.idx - b.idx;
              return ascending ? cmp : -cmp;
            });
            for (var m = 0; m < indexed.length; m++) {
              tbody.appendChild(indexed[m].row);
            }

            // Show indicator
            var indicator2 = thEl.querySelector(".sort-indicator");
            if (!indicator2) {
              indicator2 = document.createElement("span");
              indicator2.className = "sort-indicator";
              indicator2.style.marginLeft = "0.3em";
              thEl.appendChild(indicator2);
            }
            indicator2.textContent = ascending ? " \u25B2" : " \u25BC";
          }

          // Re-apply heatmap after sort
          applyHeatmap(table);
        };
      })(i, th));

      // Add empty indicator span
      var span = document.createElement("span");
      span.className = "sort-indicator";
      span.style.marginLeft = "0.3em";
      th.appendChild(span);
    }
  }

  function init() {
    var table = document.querySelector(".benchmark-table");
    if (!table) return;
    applyHeatmap(table);
    initSort(table);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
