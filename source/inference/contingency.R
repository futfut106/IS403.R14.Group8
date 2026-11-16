# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Shared statistical functions, parallel to contingency.py.
# Source this file from an inference script; no model fitting is performed.
ct_records <- function(x) {
  ev_numeric(x,"source_record",counts=TRUE)
  ev_require(all(x$source_record > 0) && !anyDuplicated(x$source_record),"Invalid/duplicate source_record.")
  ev_require(!anyNA(x[c("county","vehicle_type")]) && all(x$vehicle_type %in% c("BEV","PHEV")),"Invalid county or vehicle type.")
}
ct_p <- function(p) {
  ev_require(is.finite(p) && p >= 0 && p <= 1,"Invalid p-value.")
  list(p_value=if(p==0) NA_real_ else p,
       p_display=if(p==0) "<1e-300 (numerical underflow)" else sprintf("%.8g",p),
       p_numerical_underflow=p==0,p_value_upper_bound=if(p==0) 1e-300 else NA_real_,
       nominal_alpha=0.05,reject_h0=p<0.05)
}
ct_chisq <- function(tab,hypothesis,sample,force_monte_carlo=FALSE,B=99999L,seed=42L) {
  tab <- as.matrix(tab)
  ev_require(length(dim(tab))==2 && min(dim(tab))>=2 && all(is.finite(tab)) && all(tab>=0 & tab==floor(tab)),"Invalid contingency counts.")
  ev_require(all(rowSums(tab)>0) && all(colSums(tab)>0),"Empty contingency margin.")
  if(is.null(rownames(tab))) rownames(tab)<-as.character(seq_len(nrow(tab)))
  if(is.null(colnames(tab))) colnames(tab)<-as.character(seq_len(ncol(tab)))
  expected <- outer(rowSums(tab),colSums(tab))/sum(tab)
  statistic <- sum((tab-expected)^2/expected)
  use_mc <- force_monte_carlo || any(expected<5)
  if(use_mc) {
    ev_require(B>=9999 && B==floor(B),"At least 9999 simulations required.")
    had_seed <- exists(".Random.seed",envir=.GlobalEnv,inherits=FALSE)
    if(had_seed) saved_seed <- get(".Random.seed",envir=.GlobalEnv)
    saved_kind <- RNGkind()
    on.exit({do.call(RNGkind,as.list(saved_kind)); if(had_seed) assign(".Random.seed",saved_seed,envir=.GlobalEnv) else if(exists(".Random.seed",envir=.GlobalEnv,inherits=FALSE)) rm(".Random.seed",envir=.GlobalEnv)},add=TRUE)
    RNGkind("Mersenne-Twister","Inversion","Rejection"); set.seed(seed)
    fit <- suppressWarnings(stats::chisq.test(tab,correct=FALSE,simulate.p.value=TRUE,B=B))
    p <- fit$p.value
  } else p <- stats::pchisq(statistic,(nrow(tab)-1)*(ncol(tab)-1),lower.tail=FALSE)
  resolution <- if(use_mc) 1/(B+1) else NA_real_
  row <- c(list(hypothesis=hypothesis,sample=sample,status="computed",statistic_name="Pearson chi-square",
    statistic=statistic,n=sum(tab),table_rows=nrow(tab),table_columns=ncol(tab),
    df_theoretical=(nrow(tab)-1)*(ncol(tab)-1),p_method=if(use_mc) "Monte Carlo, fixed margins" else "asymptotic chi-square"),
    ct_p(p),list(effect_name="Cramers V",effect_size=sqrt(statistic/(sum(tab)*min(dim(tab)-1))),
    effect_definition="sqrt(chi_square / (N * min(rows-1, columns-1))); N is the sum of observed counts.",
    expected_min=min(expected),expected_cells_lt_5=sum(expected<5),expected_cells_lt_1=sum(expected<1),
    expected_cell_count=length(expected),observed_zero_cells=sum(tab==0),yates_correction=FALSE,
    mc_resamples=if(use_mc) B else NA_integer_,mc_seed=if(use_mc) seed else NA_integer_,
    mc_resolution=resolution,mc_at_resolution_limit=use_mc && abs(p-resolution)<1e-15,
    mc_engine=if(use_mc) "R chisq.test/Patefield; Mersenne-Twister" else NA_character_))
  if(row$mc_at_resolution_limit) row$p_display <- paste0(sprintf("%.8g",p)," (Monte Carlo resolution limit)")
  cells <- do.call(rbind,lapply(seq_len(nrow(tab)),function(i) do.call(rbind,lapply(seq_len(ncol(tab)),function(j)
    data.frame(hypothesis=hypothesis,sample=sample,row_label=rownames(tab)[i],column_label=colnames(tab)[j],
      observed=tab[i,j],expected=expected[i,j],expected_lt_5=expected[i,j]<5,
      row_total=sum(tab[i,]),column_total=sum(tab[,j]),n=sum(tab),stringsAsFactors=FALSE)))))
  list(row=row,cells=cells)
}
ct_compare <- function(tables,reference_dir,keys,test_file) {
  if(is.null(reference_dir)) return(NULL)
  a<-tables[[test_file]];b<-ev_read(file.path(reference_dir,test_file))
  # Underflow flags describe a numerical library, not a different hypothesis result.
  excluded<-c("p_value","p_display","p_numerical_underflow","p_value_upper_bound","effect_definition","mc_engine","mc_batch")
  columns<-list();columns[[test_file]]<-setdiff(names(a),excluded)
  checks<-ev_compare(tables,reference_dir,keys,columns)
  rows<-lapply(seq_len(nrow(a)),function(i) {
    j<-which(b$hypothesis==a$hypothesis[i] & b$sample==a$sample[i]);ev_require(length(j)==1,"Missing p-value comparison row.")
    p<-a$p_value[i];q<-b$p_value[j];u<-a$p_numerical_underflow[i];v<-ev_bool(b$p_numerical_underflow[j],"p_numerical_underflow")
    simulated<-grepl("Monte Carlo",a$p_method[i]);undefined<-a$status[i]!="computed"
    if(undefined) ok<-is.na(p) && is.na(q)
    else if(simulated) {
      # The two languages do not share random draws. Require the same decision,
      # simulation count and resolution, all separately checked above.
      ok<-identical(a$reject_h0[i],ev_bool(b$reject_h0[j],"reject_h0"))
    } else if(u && v) ok<-TRUE
    else if(u) ok<-is.finite(q) && q<a$p_value_upper_bound[i]
    else if(v) ok<-is.finite(p) && p<b$p_value_upper_bound[j]
    else ok<-is.finite(p) && is.finite(q) && abs(p-q)<=1e-300+1e-7*abs(q)
    ev_require(ok,paste("P-value interpretation differs:",a$hypothesis[i],a$sample[i]))
    data.frame(file=test_file,column=paste(a$hypothesis[i],a$sample[i],if(simulated) "Monte Carlo decision (independent draws)" else "p-value (underflow-aware)"),passed=ok,
      max_absolute_difference=if(is.finite(p) && is.finite(q)) abs(p-q) else NA_real_)
  })
  rbind(checks,do.call(rbind,rows))
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
