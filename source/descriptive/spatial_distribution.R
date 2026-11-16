# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Spatial summaries in R; Population shares and History rates have separate denominators.
# Usage: Rscript spatial_distribution.R --population-clean FILE --history-clean FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]
sp_load_population <- function(path) {
  p <- ev_read(path)
  expected <- c("County", "City", "State", "Postal Code", "Model Year", "Make", "Model",
    "Electric Vehicle Type", "Clean Alternative Fuel Vehicle (CAFV) Eligibility", "Electric Range", "Base MSRP")
  ev_require(identical(names(p), expected) && all(!is.na(p$State) & p$State == "WA"), "Unexpected Population schema/scope.")
  ev_require(!anyNA(p[c("County", "Electric Vehicle Type")]), "Missing county or vehicle type.")
  ev_require(all(p[["Electric Vehicle Type"]] %in% c("Battery Electric Vehicle (BEV)", "Plug-in Hybrid Electric Vehicle (PHEV)")), "Unknown vehicle type.")
  p
}
sp_build <- function(p, h, snapshot = "2023-11-30") {
  ev_require(setequal(p$County, h$County), "Population and History county coverage differs.")
  ev_require(snapshot %in% h$Date, "History snapshot month unavailable.")
  typ <- ifelse(p[["Electric Vehicle Type"]] == "Battery Electric Vehicle (BEV)", "bev", "phev")
  ct <- table(factor(p$County, levels = sort(unique(p$County))), factor(typ, levels = c("bev", "phev")))
  county <- data.frame(county = rownames(ct), bev = as.numeric(ct[, 1]), phev = as.numeric(ct[, 2]))
  total <- nrow(p); county$ev_count <- county$bev + county$phev
  county$share_pct <- 100 * county$ev_count / total
  county$bev_share_pct <- 100 * county$bev / county$ev_count
  county$phev_share_pct <- 100 * county$phev / county$ev_count
  county <- county[order(-county$ev_count, county$county, method = "radix"), ]; county$rank <- seq_len(nrow(county))
  county$cumulative_share_pct <- cumsum(county$share_pct); county$population_n <- total
  # Integer encodings preserve missing-city groups without text-key collisions.
  city_key <- p[c("County", "City")]; city <- unique(city_key)
  county_levels <- unique(city_key$County); city_levels <- unique(city_key$City)
  key_text <- function(x) paste(match(x$County,county_levels), match(x$City,city_levels), sep = ":")
  city$ev_count <- tabulate(match(key_text(city_key), key_text(city)), nbins = nrow(city))
  names(city)[1:2] <- c("county", "city")
  city$is_missing_city <- is.na(city$city); city$share_pct <- 100 * city$ev_count / total; city$population_n <- total
  city <- city[order(-city$ev_count, city$county, city$city, na.last = TRUE, method = "radix"), ]; city$rank <- seq_len(nrow(city))
  cut <- h[h$Date == snapshot, ]; rates <- sp_aggregate(cut, "County"); names(rates)[1] <- "county"
  rates$date <- snapshot; rates$ev_pct <- 100 * rates$ev_total / rates$total_vehicles
  rates$ev_share_statewide_pct <- 100 * rates$ev_total / sum(rates$ev_total)
  rates$rank_ev_count <- rank(-rates$ev_total, ties.method = "min"); rates$rank_ev_pct <- rank(-rates$ev_pct, ties.method = "min")
  rates <- rates[order(-rates$ev_pct, rates$county, method = "radix"), c("date", "county", sp_count_names, "ev_pct", "ev_share_statewide_pct", "rank_ev_count", "rank_ev_pct")]
  usage <- sp_aggregate(cut, "Vehicle Primary Use"); names(usage)[1] <- "vehicle_primary_use"
  usage$date <- snapshot; usage$ev_pct <- 100 * usage$ev_total / usage$total_vehicles
  usage$bev_share_ev_pct <- ifelse(usage$ev_total > 0, 100 * usage$bev / usage$ev_total, NA_real_)
  usage$ev_share_statewide_pct <- 100 * usage$ev_total / sum(usage$ev_total)
  usage$vehicle_share_statewide_pct <- 100 * usage$total_vehicles / sum(usage$total_vehicles)
  usage <- usage[, c("date", "vehicle_primary_use", sp_count_names, "ev_pct", "bev_share_ev_pct", "ev_share_statewide_pct", "vehicle_share_statewide_pct")]
  ev_require(sum(city$ev_count) == total && sum(county$ev_count) == total, "Spatial aggregation lost Population rows.")
  list(county_summary.csv = county, city_summary.csv = city, county_ev_rates.csv = rates, usage_type_summary.csv = usage)
}
sp_plots <- function(t) list(
  population_by_county.png = function() { x <- head(t$county_summary.csv, 10); par(mar=c(5,9,4,2)); barplot(rev(x$ev_count), names.arg=rev(x$county), horiz=TRUE, col="#087E81", xlab="Population records", main="EV counts by county") },
  population_by_city.png = function() { x <- head(t$city_summary.csv, 10); par(mar=c(5,13,4,2)); barplot(rev(x$ev_count), names.arg=rev(paste(x$county,x$city,sep=" / ")), horiz=TRUE,col="#087E81",xlab="Population records",main="County-City pairs") },
  county_ev_rates.png = function() { x <- head(t$county_ev_rates.csv, 10); par(mar=c(5,9,4,2)); barplot(rev(x$ev_pct),names.arg=rev(x$county),horiz=TRUE,col="#367AB5",xlab="EV / total vehicles (%)",main=paste("County EV rates:",x$date[1])) },
  usage_type_comparison.png = function() { x <- t$usage_type_summary.csv; barplot(x$ev_pct,names.arg=x$vehicle_primary_use,col=c("#087E81","#DB963E"),ylab="EV / total vehicles within use group (%)",main=paste("Passenger and Truck:",x$date[1])) })
sp_main <- function() {
  a <- ev_cli(c("population-clean", "history-clean", "output-dir", "figures-dir"), c("python-results-dir", "snapshot-date"),
    "Rscript spatial_distribution.R --population-clean FILE --history-clean FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR] [--snapshot-date YYYY-MM-DD]")
  if (is.null(a)) return(invisible(NULL))
  snapshot <- if (is.null(a[["snapshot-date"]])) "2023-11-30" else a[["snapshot-date"]]
  t <- sp_build(sp_load_population(a[["population-clean"]]), sp_load_history(a[["history-clean"]]), snapshot)
  keys <- list(county_summary.csv="county",city_summary.csv=c("county","city"),county_ev_rates.csv=c("date","county"),usage_type_summary.csv=c("date","vehicle_primary_use"))
  checks <- ev_compare(t, a[["python-results-dir"]], keys)
  ev_publish(t,a[["output-dir"]],a[["figures-dir"]],sp_plots(t),c(a[["population-clean"]],a[["history-clean"]]),"spatial_distribution",checks)
}

sp_history_columns <- c("Date", "County", "State", "Vehicle Primary Use", "Battery Electric Vehicles (BEVs)",
  "Plug-In Hybrid Electric Vehicles (PHEVs)", "Electric Vehicle (EV) Total", "Non-Electric Vehicle Total",
  "Total Vehicles", "Percent Electric Vehicles")
sp_count_names <- c("bev", "phev", "ev_total", "non_ev", "total_vehicles")
sp_load_history <- function(path) {
  h <- ev_read(path, sp_history_columns)
  ev_require(!anyNA(h) && all(h$State == "WA"), "History must contain nonmissing WA rows only.")
  ev_require(setequal(unique(h[["Vehicle Primary Use"]]), c("Passenger", "Truck")), "Expected Passenger and Truck.")
  ev_numeric(h, sp_history_columns[5:9], counts = TRUE); ev_numeric(h, sp_history_columns[10])
  dates <- as.Date(h$Date, format = "%Y-%m-%d")
  ev_require(!anyNA(dates) && all(format(dates, "%Y-%m-%d") == h$Date), "Invalid ISO History dates.")
  expected <- format(seq(as.Date("2017-02-01"), by = "month", length.out = 83) - 1, "%Y-%m-%d")
  ev_require(identical(sort(unique(h$Date)), expected) && length(unique(h$County)) == 39L, "Expected 83 month ends and 39 counties.")
  key <- h[c("Date", "County", "Vehicle Primary Use")]
  ev_require(!anyDuplicated(key) && nrow(h) == 83L * 39L * 2L, "Incomplete or duplicate History grid.")
  ev_require(all(h[[5]] + h[[6]] == h[[7]]) && all(h[[7]] + h[[8]] == h[[9]]) && all(h[[9]] > 0), "History count identities failed.")
  ev_require(all(abs(round(100 * h[[7]] / h[[9]], 2) - h[[10]]) <= 1e-9), "History percentages disagree with counts.")
  h
}
sp_aggregate <- function(h, groups) {
  out <- aggregate(h[sp_history_columns[5:9]], h[groups], sum)
  names(out)[(length(groups) + 1L):ncol(out)] <- sp_count_names
  out
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

if (sys.nframe() == 0L) sp_main()
