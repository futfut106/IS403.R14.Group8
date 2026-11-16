# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# History monthly analysis in R. Stock differences are net changes, not new sales.
# Usage: Rscript monthly_trends.R --history-clean FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]
mt_lag <- function(x, k = 1L) c(rep(NA_real_, min(k, length(x))), if (length(x) > k) head(x, -k) else numeric())
mt_roll <- function(x, k, fun) vapply(seq_along(x), function(i) if (i < k || anyNA(x[(i-k+1L):i])) NA_real_ else fun(x[(i-k+1L):i]), numeric(1))
mt_build <- function(h) {
  monthly <- sp_aggregate(h, "Date"); names(monthly)[1] <- "date"
  monthly <- monthly[order(monthly$date), ]; monthly$ev_pct <- 100 * monthly$ev_total / monthly$total_vehicles
  monthly$split <- ifelse(monthly$date <= "2022-11-30", "train", "test")
  ev_require(nrow(monthly) == 83L && sum(monthly$split == "train") == 71L && sum(monthly$split == "test") == 12L, "Unexpected time split.")
  monthly$bev_share_pct <- 100 * monthly$bev / monthly$ev_total; monthly$phev_share_pct <- 100 * monthly$phev / monthly$ev_total
  growth <- list()
  for (variable in c("bev", "phev", "ev_total")) {
    prefix <- if (variable == "ev_total") "ev" else variable; v <- monthly[[variable]]
    monthly[[paste0(prefix,"_net_change")]] <- v - mt_lag(v)
    monthly[[paste0(prefix,"_mom_growth_pct")]] <- 100 * (v / mt_lag(v) - 1)
    monthly[[paste0(prefix,"_yoy_net_change")]] <- v - mt_lag(v, 12)
    monthly[[paste0(prefix,"_yoy_growth_pct")]] <- 100 * (v / mt_lag(v, 12) - 1)
    growth[[variable]] <- data.frame(series=variable,start_date=monthly$date[1],end_date=tail(monthly$date,1),
      monthly_intervals=nrow(monthly)-1L,start_vehicles=v[1],end_vehicles=tail(v,1),net_change_vehicles=tail(v,1)-v[1],
      growth_pct=100*(tail(v,1)/v[1]-1),annualized_growth_pct=100*((tail(v,1)/v[1])^(12/(nrow(monthly)-1L))-1))
  }
  monthly$ev_log_growth_pct <- c(NA_real_,diff(log(monthly$ev_total))*100)
  monthly$ev_ma12 <- mt_roll(monthly$ev_total,12,mean)
  monthly$net_change_sd12 <- mt_roll(monthly$ev_net_change,12,sd)
  annual <- monthly[substr(monthly$date,6,7)=="12" | seq_len(nrow(monthly))==nrow(monthly),
    c("date","bev","phev","ev_total","bev_yoy_net_change","bev_yoy_growth_pct","phev_yoy_net_change","phev_yoy_growth_pct","ev_yoy_net_change","ev_yoy_growth_pct")]
  annual$is_year_end <- substr(annual$date,6,7)=="12"
  ch <- monthly[!is.na(monthly$ev_net_change), ]; half <- nrow(ch)%/%2
  periods <- list(all_changes=ch,first_half=ch[seq_len(half),],second_half=ch[(half+1):nrow(ch),],train_changes=ch[ch$split=="train",],test_changes=ch[ch$split=="test",])
  period_table <- do.call(rbind,lapply(names(periods),function(name){x<-periods[[name]];data.frame(period=name,
    first_change_month=x$date[1],last_change_month=tail(x$date,1),change_intervals=nrow(x),
    mean_net_change_vehicles=mean(x$ev_net_change),std_net_change_vehicles=sd(x$ev_net_change),
    min_net_change_vehicles=min(x$ev_net_change),max_net_change_vehicles=max(x$ev_net_change),
    mean_log_growth_pct=mean(x$ev_log_growth_pct),std_log_growth_pct=sd(x$ev_log_growth_pct))}))
  largest <- ch$date[head(order(-ch$ev_net_change,seq_len(nrow(ch))),3)]
  smallest <- ch$date[head(order(ch$ev_net_change,seq_len(nrow(ch))),3)]
  notable <- monthly[monthly$date%in%c(largest,smallest),c("date","ev_total","ev_net_change","ev_mom_growth_pct","ev_yoy_growth_pct")]
  notable$selection <- ifelse(notable$date%in%largest,"largest_net_change","smallest_net_change")
  list(monthly_growth.csv=monthly,overall_growth_summary.csv=do.call(rbind,growth),annual_growth.csv=annual,
       growth_period_summary.csv=period_table,notable_months.csv=notable)
}
mt_plots <- function(t) {
  x <- t$monthly_growth.csv; dates <- as.Date(x$date)
  list(monthly_ev_population.png=function(){matplot(dates,as.matrix(x[c("ev_total","bev","phev")]),type="l",lty=1,col=c("#102D3B","#087E81","#DB963E"),lwd=2,xlab="Month",ylab="Vehicles at month end",main="Statewide EV population");legend("topleft",c("EV Total","BEV","PHEV"),col=c("#102D3B","#087E81","#DB963E"),lty=1,bty="n")},
       monthly_ev_composition.png=function(){plot(dates,x$bev_share_pct,type="l",ylim=c(0,100),col="#087E81",lwd=2,xlab="Month",ylab="Share within EV (%)",main="BEV/PHEV composition");lines(dates,x$phev_share_pct,col="#DB963E",lwd=2);legend("topright",c("BEV","PHEV"),col=c("#087E81","#DB963E"),lty=1,bty="n")},
       monthly_ev_growth.png=function(){plot(dates,x$ev_net_change,type="h",lwd=3,col="#087E81",xlab="Month",ylab="Net change in vehicles",main="Monthly EV net change (not sales)");abline(h=0,col="grey60")},
       statewide_ev_rate.png=function(){plot(dates,x$ev_pct,type="l",lwd=2,col="#367AB5",xlab="Month",ylab="EV / total vehicles (%)",main="Statewide EV penetration")})
}
mt_main <- function() {
  a <- ev_cli(c("history-clean","output-dir","figures-dir"),"python-results-dir",
    "Rscript monthly_trends.R --history-clean FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]")
  if (is.null(a)) return(invisible(NULL))
  t <- mt_build(sp_load_history(a[["history-clean"]]))
  keys <- list(monthly_growth.csv="date",overall_growth_summary.csv="series",annual_growth.csv="date",growth_period_summary.csv="period",notable_months.csv="date")
  checks <- ev_compare(t,a[["python-results-dir"]],keys)
  ev_publish(t,a[["output-dir"]],a[["figures-dir"]],mt_plots(t),a[["history-clean"]],"monthly_trends",checks)
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

if (sys.nframe() == 0L) mt_main()
