# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Population descriptive analysis in R, parallel to vehicle_characteristics.py.
# Usage: Rscript vehicle_characteristics.R --population-clean FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]

vc_columns <- c("County", "City", "State", "Postal Code", "Model Year", "Make", "Model",
  "Electric Vehicle Type", "Clean Alternative Fuel Vehicle (CAFV) Eligibility", "Electric Range", "Base MSRP")
vc_type <- function(x) {
  map <- c("Battery Electric Vehicle (BEV)" = "BEV", "Plug-in Hybrid Electric Vehicle (PHEV)" = "PHEV")
  ev_require(all(is.na(x) | x %in% names(map)), "Unexpected vehicle type.")
  unname(map[x])
}
vc_load <- function(path) {
  x <- ev_read(path, vc_columns)
  ev_require(!anyNA(x$State) && all(x$State == "WA"), "Population must contain WA only.")
  ev_numeric(x, c("Model Year", "Electric Range"), missing = TRUE)
  year <- x[["Model Year"]]; range <- x[["Electric Range"]]
  ev_require(all(is.na(year) | (year > 0 & year == floor(year))), "Invalid Model Year.")
  ev_require(all(is.na(range) | range > 0), "Range must be positive or missing; clean raw separately.")
  vc_type(x[["Electric Vehicle Type"]]); x
}
vc_frequency <- function(x, name, chronological = FALSE) {
  vals <- unique(x)
  counts <- vapply(vals, function(v) if (is.na(v)) sum(is.na(x)) else sum(x == v, na.rm = TRUE), numeric(1))
  out <- data.frame(value = vals, count = counts, share_pct = 100 * counts / length(x),
                    population_n = length(x), is_missing = is.na(vals), stringsAsFactors = FALSE)
  names(out)[1] <- name
  o <- if (chronological) order(out[[name]], na.last = TRUE) else order(out$is_missing, -out$count, out[[name]], na.last = TRUE, method = "radix")
  out[o, , drop = FALSE]
}
vc_build <- function(x) {
  types <- vc_type(x[["Electric Vehicle Type"]])
  tables <- list(
    vehicle_type_frequency.csv = vc_frequency(types, "vehicle_type"),
    cafv_frequency.csv = vc_frequency(x[["Clean Alternative Fuel Vehicle (CAFV) Eligibility"]], "cafv_status"),
    make_frequency.csv = vc_frequency(x$Make, "make"),
    model_year_frequency.csv = vc_frequency(x[["Model Year"]], "model_year", TRUE))
  groups <- list(ALL = x, BEV = x[!is.na(types) & types == "BEV", ], PHEV = x[!is.na(types) & types == "PHEV", ])
  if (anyNA(types)) groups$MISSING_TYPE <- x[is.na(types), ]
  tables$range_summary.csv <- do.call(rbind, lapply(names(groups), function(name) {
    all <- groups[[name]][["Electric Range"]]; v <- all[!is.na(all)]; n <- length(v); total <- length(all)
    q <- if (n) as.numeric(quantile(v, c(.25, .75), type = 7)) else c(NA_real_, NA_real_)
    data.frame(group = name, total_n = total, valid_n = n, missing_n = total - n,
      valid_pct = 100 * n / total, missing_pct = 100 * (total - n) / total,
      mean_miles = if (n) mean(v) else NA_real_, median_miles = if (n) median(v) else NA_real_,
      std_miles = if (n > 1) sd(v) else NA_real_, min_miles = if (n) min(v) else NA_real_,
      q1_miles = q[1], q3_miles = q[2], iqr_miles = q[2] - q[1], max_miles = if (n) max(v) else NA_real_)
  }))
  tables
}
vc_plots <- function(x, tables) list(
  vehicle_type_share.png = function() {
    t <- tables$vehicle_type_frequency.csv
    barplot(t$share_pct, names.arg = t$vehicle_type, col = c("#087E81", "#DB963E"), ylim = c(0, 100),
            ylab = "Share of Population (%)", main = "BEV/PHEV composition")
  },
  top_makes.png = function() {
    t <- head(tables$make_frequency.csv, 10); par(mar = c(5, 9, 4, 2))
    barplot(rev(t$count), names.arg = rev(t$make), horiz = TRUE, col = "#087E81", xlab = "Population records", main = "Top manufacturers")
  },
  model_year_distribution.png = function() {
    t <- tables$model_year_frequency.csv; t <- t[!is.na(t$model_year), ]
    barplot(t$count, names.arg = t$model_year, las = 2, col = "#367AB5", ylab = "Population records", main = "Model Year (not sales year)")
  },
  range_by_vehicle_type.png = function() {
    types <- vc_type(x[["Electric Vehicle Type"]]); valid <- !is.na(x[["Electric Range"]]) & !is.na(types)
    boxplot(x[["Electric Range"]][valid] ~ factor(types[valid], levels = c("BEV", "PHEV")),
            col = c("#087E81", "#DB963E"), xlab="Vehicle type", ylab = "Electric Range (miles)", main = "Range among nonmissing observations")
  })
vc_main <- function() {
  a <- ev_cli(c("population-clean", "output-dir", "figures-dir"), "python-results-dir",
    "Rscript vehicle_characteristics.R --population-clean FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]")
  if (is.null(a)) return(invisible(NULL))
  x <- vc_load(a[["population-clean"]]); t <- vc_build(x)
  keys <- setNames(lapply(names(t), function(n) names(t[[n]])[1]), names(t))
  checks <- ev_compare(t, a[["python-results-dir"]], keys)
  ev_publish(t, a[["output-dir"]], a[["figures-dir"]], vc_plots(x, t), a[["population-clean"]], "vehicle_characteristics", checks)
}

# Standalone command-line support. No package installation or model fitting.
ev_require <- function(ok, message) {
  if (length(ok) != 1L || is.na(ok) || !ok) stop(message, call. = FALSE)
}
ev_read <- function(path, columns = NULL) {
  ev_require(file.exists(path) && !dir.exists(path), paste("CSV not found:", path))
  x <- read.csv(path, check.names = FALSE, stringsAsFactors = FALSE,
                fileEncoding = "UTF-8-BOM", na.strings = "")
  if (!is.null(columns)) ev_require(identical(names(x), columns), paste("Unexpected CSV columns:", path))
  ev_require(nrow(x) > 0L, paste("Empty CSV:", path))
  x
}
ev_cli <- function(required, optional = character(), usage) {
  a <- commandArgs(trailingOnly = TRUE)
  if (length(a) == 0L || identical(a, "--help")) { cat(usage, "\n"); return(NULL) }
  ev_require(length(a) %% 2L == 0L, "Use --name value pairs; quote paths containing spaces.")
  keys <- sub("^--", "", a[seq(1L, length(a), 2L)])
  ev_require(all(grepl("^--", a[seq(1L, length(a), 2L)])), "Expected --name value pairs.")
  ev_require(!anyDuplicated(keys) && all(keys %in% c(required, optional)), "Duplicate or unknown command-line argument.")
  z <- as.list(a[seq(2L, length(a), 2L)]); names(z) <- keys
  ev_require(all(required %in% keys), paste("Required:", paste(paste0("--", required), collapse = ", ")))
  z
}
ev_numeric <- function(x, columns, missing = FALSE, counts = FALSE) {
  for (column in columns) {
    ev_require(is.numeric(x[[column]]), paste("Expected numeric column:", column))
    v <- x[[column]]
    ev_require(all(is.finite(v) | (missing & is.na(v))), paste("Missing/nonfinite numeric column:", column))
    if (counts) ev_require(all(v >= 0 & v == floor(v)), paste("Expected nonnegative integer counts:", column))
  }
  invisible(x)
}
ev_bool <- function(x, label) {
  v <- toupper(as.character(x))
  ev_require(!anyNA(v) && all(v %in% c("TRUE", "FALSE")), paste("Invalid Boolean flag:", label))
  v == "TRUE"
}
ev_rbind <- function(rows) {
  cols <- unique(unlist(lapply(rows, names)))
  out <- lapply(rows, function(x) {
    if (!is.data.frame(x)) x <- as.data.frame(x, stringsAsFactors = FALSE, check.names = FALSE)
    for (n in setdiff(cols, names(x))) x[[n]] <- NA
    x[, cols, drop = FALSE]
  })
  rownames_out <- do.call(rbind, out); rownames(rownames_out) <- NULL; rownames_out
}
ev_preflight <- function(paths, inputs) {
  resolved <- normalizePath(paths, winslash = "/", mustWork = FALSE)
  ev_require(!anyDuplicated(resolved), "Output paths must be distinct.")
  ev_require(!any(file.exists(paths) | dir.exists(paths)), "Output already exists; choose a new destination for this run.")
  sources <- normalizePath(inputs, winslash = "/", mustWork = TRUE)
  ev_require(!any(resolved %in% sources), "Outputs must not overwrite inputs.")
}
ev_png <- function(path, draw, width = 1500, height = 900) {
  grDevices::png(path, width = width, height = height, res = 140,
                 type = if (capabilities("cairo")) "cairo" else if (.Platform$OS.type == "windows") "windows" else "Xlib")
  on.exit(grDevices::dev.off(), add = TRUE)
  graphics::par(mar = c(5, 6, 4, 2), las = 1, cex = 1.05)
  draw()
}
ev_publish <- function(tables, output_dir, figure_dir, plots, inputs, module, checks = NULL) {
  if (!is.null(checks)) tables[[paste0(module, "_python_r_checks.csv")]] <- checks
  destinations <- c(file.path(output_dir, names(tables)), file.path(figure_dir, names(plots)),
                    file.path(output_dir, paste0(module, "_session.txt")))
  ev_preflight(destinations, inputs)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
  for (name in names(tables)) write.csv(tables[[name]], file.path(output_dir, name),
                                       row.names = FALSE, na = "", fileEncoding = "UTF-8")
  for (name in names(plots)) ev_png(file.path(figure_dir, name), plots[[name]])
  writeLines(c(paste("Module:", module), "Models fitted/refitted: none", capture.output(sessionInfo())),
             file.path(output_dir, paste0(module, "_session.txt")), useBytes = TRUE)
  cat("Completed:", module, "| tables:", length(tables), "| figures:", length(plots), "\n")
  invisible(tables)
}
ev_compare <- function(tables, reference_dir, keys, columns = NULL) {
  if (is.null(reference_dir)) return(NULL)
  checks <- list()
  for (name in names(tables)) {
    a <- tables[[name]]; b <- ev_read(file.path(reference_dir, name)); key <- keys[[name]]
    ev_require(!is.null(key) && all(key %in% names(a)) && all(key %in% names(b)), paste("Missing comparison keys:", name))
    ev_require(!anyDuplicated(a[key]) && !anyDuplicated(b[key]), paste("Duplicate comparison keys:", name))
    ev_require(nrow(a) == nrow(b), paste("Row count differs:", name))
    ord <- function(x) do.call(order, c(unname(x[key]), list(na.last = TRUE, method = "radix")))
    a <- a[ord(a), , drop = FALSE]; b <- b[ord(b), , drop = FALSE]
    cols <- if (is.null(columns) || is.null(columns[[name]])) names(a) else columns[[name]]
    ev_require(all(cols %in% names(b)), paste("Reference columns differ:", name))
    for (column in cols) {
      x <- a[[column]]; y <- b[[column]]
      if (is.logical(x) && !all(is.na(y))) { parsed <- rep(NA, length(y)); parsed[!is.na(y)] <- ev_bool(y[!is.na(y)],column); y <- parsed }
      missing_ok <- identical(is.na(x), is.na(y)); keep <- !is.na(x) & !is.na(y)
      delta <- NA_real_
      if (is.numeric(x) && (is.numeric(y) || all(is.na(y)))) {
        delta <- if (any(keep)) max(abs(x[keep] - y[keep])) else 0
        if (column == "p_value") {
          ok <- missing_ok && all(abs(x[keep] - y[keep]) <= 1e-300 + 1e-7 * abs(y[keep]))
        } else {
          ok <- missing_ok && all(abs(x[keep] - y[keep]) <= 1e-8 + 1e-10 * abs(y[keep]))
        }
      } else ok <- missing_ok && identical(as.character(x[keep]), as.character(y[keep]))
      checks[[length(checks) + 1L]] <- data.frame(file = name, column = column,
        passed = ok, max_absolute_difference = delta, stringsAsFactors = FALSE)
    }
  }
  result <- do.call(rbind, checks)
  if (!all(result$passed)) print(result[!result$passed, , drop = FALSE])
  ev_require(all(result$passed), "Python/R comparison failed; inspect inputs and settings rather than changing results.")
  result
}

if (sys.nframe() == 0L) vc_main()
