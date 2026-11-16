# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Evaluate locked Python forecasts in R. No model fitting or model selection.
# Selection summary is input metadata; all errors and metrics are recomputed.
fc_models <- c("Naive","Drift","ARIMA","SARIMA","Ridge","Random Forest","SVR","XGBoost")
fc_metrics <- function(actual,pred) {
  ev_require(length(actual)==length(pred) && length(actual)>0 && all(is.finite(c(actual,pred))),"Invalid metric vectors.")
  error<-actual-pred; denom<-abs(actual)+abs(pred)
  list(rmse=sqrt(mean(error^2)),mae=mean(abs(error)),smape=mean(ifelse(denom==0,0,200*abs(error)/denom)),bias=mean(error))
}
fc_load <- function(series_path,forecast_dir) {
  series<-ev_read(series_path)
  ev_require(all(c("date","ev_total","split") %in% names(series)),"Series schema is missing required columns.")
  ev_numeric(series,"ev_total");dates<-as.character(seq(as.Date("2017-02-01"),by="month",length.out=83)-1)
  ev_require(identical(series$date,dates) && all(series$ev_total>0) && identical(as.character(series$split),c(rep("train",71),rep("test",12))),"Series dates/train-test split differ from locked design.")
  selected<-ev_read(file.path(forecast_dir,"comparison_selection_summary.csv"))
  ev_require(all(c("model","config_id","train_end","train_months") %in% names(selected)) && nrow(selected)==6 && !anyDuplicated(selected$model) && setequal(selected$model,fc_models[3:8]),"Invalid selection metadata.")
  ev_require(all(selected$train_end=="2022-11-30" & selected$train_months==71),"Selection metadata uses a different training period.")
  names_in<-paste0("forecast_",c("baselines","arima","sarima","ridge","random_forest","svr","xgboost"),".csv")
  schema<-c("model","config_id","date","origin","horizon","actual","pred","target_transform","evaluation_role","lower_95","upper_95","interval_level")
  raw<-do.call(rbind,lapply(names_in,function(n) ev_read(file.path(forecast_dir,n),schema)))
  ev_require(!anyNA(raw[c("model","config_id","date","origin","horizon","actual","pred","target_transform","evaluation_role")]),"Missing forecast identifiers or values.")
  ev_require(all(raw$model %in% fc_models) && all(raw$evaluation_role %in% c("baseline","selected","candidate_reference")),"Unexpected model/role.")
  ev_require(all(raw$model[raw$evaluation_role=="candidate_reference"]=="SARIMA"),"Only unselected SARIMA candidates may have reference role.")
  z<-raw[raw$evaluation_role %in% c("baseline","selected"),]
  ev_numeric(z,c("actual","pred","horizon"));ev_require(nrow(z)==96 && !anyDuplicated(z[c("model","date")]),"Expected 96 unique selected/baseline forecasts.")
  test<-series[series$split=="test",]
  for(model in fc_models) {
    w<-z[z$model==model,];w<-w[order(w$horizon),]
    id<-if(model=="Naive") "NAIVE" else if(model=="Drift") "DRIFT" else selected$config_id[match(model,selected$model)]
    ev_require(nrow(w)==12 && identical(as.numeric(w$horizon),as.numeric(1:12)) && identical(w$date,test$date),paste("Incorrect forecast horizon:",model))
    ev_require(all(w$config_id==id & w$origin=="2022-11-30" & w$target_transform=="level" & w$pred>0) && all(w$actual==test$ev_total),paste("Forecast metadata/actuals mismatch:",model))
    ev_require(all(w$evaluation_role==if(model %in% fc_models[1:2]) "baseline" else "selected"),"Forecast role disagrees with model.")
    if(model %in% c("ARIMA","SARIMA")) {
      ev_numeric(w,c("lower_95","upper_95","interval_level"))
      ev_require(all(w$lower_95<=w$pred & w$upper_95>=w$pred & w$interval_level==.95),"Invalid prediction intervals.")
    } else ev_require(all(is.na(w[c("lower_95","upper_95","interval_level")])),"Unexpected interval for model without interval output.")
  }
  z<-z[order(match(z$model,fc_models),z$horizon),];rownames(z)<-NULL
  list(forecasts=z,series=series,selection=selected,inputs=c(series_path,file.path(forecast_dir,c(names_in,"comparison_selection_summary.csv"))))
}
fc_build <- function(data) {
  x<-data$forecasts;err<-x$actual-x$pred;denom<-abs(x$actual)+abs(x$pred)
  errors<-x;errors$error<-err;errors$absolute_error<-abs(err);errors$squared_error<-err^2
  errors$smape_component<-ifelse(denom==0,0,200*abs(err)/denom)
  rows<-lapply(fc_models,function(model) {
    w<-x[x$model==model,]
    c(list(model=model,config_id=w$config_id[1],n_test=nrow(w),origin=w$origin[1]),fc_metrics(w$actual,w$pred),
      list(months_underpredicted=sum(w$actual>w$pred),months_overpredicted=sum(w$actual<w$pred)))
  })
  metrics<-ev_rbind(rows)
  for(metric in c("rmse","mae","smape")) {
    metrics[[paste0("rank_",metric)]]<-rank(metrics[[metric]],ties.method="min")
    for(baseline in c("naive","drift")) metrics[[paste0(metric,"_improvement_vs_",baseline,"_pct")]]<-100*(1-metrics[[metric]]/metrics[[metric]][match(if(baseline=="naive") "Naive" else "Drift",metrics$model)])
  }
  metrics<-metrics[order(metrics$rmse,metrics$model),];rownames(metrics)<-NULL
  predictions<-data$series[data$series$split=="test",c("date","ev_total")];names(predictions)[2]<-"actual"
  for(model in fc_models) predictions[[model]]<-x$pred[x$model==model]
  cumulative<-ev_rbind(unlist(lapply(fc_models,function(model) {
    w<-x[x$model==model,]
    lapply(1:12,function(h) c(list(model=model,config_id=w$config_id[1],through_date=w$date[h],through_horizon=h),fc_metrics(w$actual[1:h],w$pred[1:h])))
  }),recursive=FALSE))
  intervals<-ev_rbind(lapply(c("ARIMA","SARIMA"),function(model) {
    w<-x[x$model==model,];covered<-sum(w$actual>=w$lower_95 & w$actual<=w$upper_95)
    list(model=model,config_id=w$config_id[1],n_test=nrow(w),nominal_level=.95,covered_months=covered,observed_coverage=covered/nrow(w),mean_width=mean(w$upper_95-w$lower_95))
  }))
  list(comparison_metrics.csv=metrics,comparison_errors.csv=errors,comparison_predictions.csv=predictions,
       comparison_cumulative_metrics.csv=cumulative,comparison_interval_summary.csv=intervals)
}
fc_plots <- function(tables) {
  m<-tables$comparison_metrics.csv;p<-tables$comparison_predictions.csv;e<-tables$comparison_errors.csv;c<-tables$comparison_cumulative_metrics.csv
  cols<-c("#666666","#999999","#0072b2","#009e73","#d55e00","#e69f00","#cc79a7","#56b4e9")
  list(comparison_accuracy.png=function() {
    par(mfrow=c(1,2),mar=c(10,5,4,1),las=2)
    for(metric in c("rmse","mae")) barplot(m[[metric]],names.arg=m$model,col=cols[match(m$model,fc_models)],ylab=toupper(metric),main=paste(toupper(metric),"on 12 held-out months"))
  },comparison_forecasts.png=function() {
    par(mfrow=c(2,4),mar=c(4,4,3,1),las=1)
    for(i in seq_along(fc_models)) {model<-fc_models[i];plot(1:12,p$actual,type="l",lwd=2,ylim=range(c(p$actual,p[[model]])),xlab="Test horizon",ylab="EV count",main=model);lines(1:12,p[[model]],col=cols[i],lwd=2,lty=2);legend("topleft",c("Actual","Prediction"),col=c("black",cols[i]),lty=c(1,2),bty="n",cex=.6)}
  },comparison_monthly_errors.png=function() {
    z<-sapply(fc_models,function(model)e$error[e$model==model]);lim<-max(abs(z))
    palette<-colorRampPalette(c("#2166ac","white","#b2182b"))(101)
    layout(matrix(c(1,2),nrow=1),widths=c(8,1))
    par(mar=c(5,10,3,1));image(1:12,1:8,z,zlim=c(-lim,lim),col=palette,axes=FALSE,xlab="Test horizon",ylab="",main="Actual minus prediction (vehicles)")
    axis(1,at=1:12);axis(2,at=1:8,labels=fc_models,las=1)
    par(mar=c(5,1,3,4));scale<-seq(-lim,lim,length.out=101)
    image(1,scale,matrix(scale,nrow=1),col=palette,axes=FALSE,xlab="",ylab="");axis(4,at=pretty(c(-lim,lim)),las=1)
  },comparison_cumulative_rmse.png=function() {
    par(mfrow=c(1,2),mar=c(5,5,4,1));for(models in list(fc_models,fc_models[3:8])) {
      z<-sapply(models,function(model)c$rmse[c$model==model]);matplot(1:12,z,type="l",lty=1,lwd=2,col=cols[match(models,fc_models)],xlab="Through test horizon",ylab="Cumulative RMSE",main=if(length(models)==8) "All methods" else "Selected models")
      legend("topleft",models,col=cols[match(models,fc_models)],lty=1,bty="n",cex=.65)
    }
  })
}
fc_main <- function() {
  a<-ev_cli(c("series","forecast-dir","output-dir","figures-dir"),"python-results-dir",
    "Rscript evaluate_forecasts.R --series FILE --forecast-dir DIR --output-dir DIR --figures-dir DIR [--python-results-dir DIR]")
  if(is.null(a)) return(invisible(NULL))
  data<-fc_load(a[["series"]],a[["forecast-dir"]]);tables<-fc_build(data)
  keys<-list(comparison_metrics.csv="model",comparison_errors.csv=c("model","date"),comparison_predictions.csv="date",
    comparison_cumulative_metrics.csv=c("model","through_horizon"),comparison_interval_summary.csv="model")
  checks<-ev_compare(tables,a[["python-results-dir"]],keys)
  ev_publish(tables,a[["output-dir"]],a[["figures-dir"]],fc_plots(tables),data$inputs,"evaluate_forecasts",checks)
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

if (sys.nframe() == 0L) fc_main()
