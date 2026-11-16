# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Locate the sibling utility both under Rscript and when sourced interactively.
ct_path <- local({
  frames <- sys.frames(); files <- unlist(lapply(frames,function(f) f$ofile))
  if(length(files)) tail(files,1) else sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
})
if(is.na(ct_path) || !nzchar(ct_path)) stop("Source this script by its file path.",call.=FALSE)
source(file.path(dirname(normalizePath(ct_path,mustWork=TRUE)),"contingency.R"),local=TRUE)

# H1 Mann-Whitney and H2 Spearman, parallel to range_tests.py.
# Input is the prepared range sample, never a saved test result.
rg_load <- function(path) {
  x <- ev_read(path,c("source_record","county","vehicle_type","model_year","electric_range","h1_year_le_2020","h2_valid"))
  ct_records(x); ev_numeric(x,"electric_range"); ev_numeric(x,"model_year",missing=TRUE)
  ev_require(all(x$electric_range>0) && all(is.na(x$model_year) | (x$model_year>0 & x$model_year==floor(x$model_year))),"Invalid range/model year.")
  x$h1_year_le_2020 <- ev_bool(x$h1_year_le_2020,"h1_year_le_2020")
  x$h2_valid <- ev_bool(x$h2_valid,"h2_valid")
  ev_require(all(x$h2_valid==!is.na(x$model_year)) && all(x$h1_year_le_2020==(!is.na(x$model_year) & x$model_year<=2020)),"Prepared range flags disagree with values.")
  x
}
rg_build <- function(x) {
  rows <- list()
  for(sample in c("primary","year_le_2020")) {
    z <- if(sample=="primary") x else x[x$h1_year_le_2020,]
    a <- z$electric_range[z$vehicle_type=="BEV"]; b <- z$electric_range[z$vehicle_type=="PHEV"]
    ev_require(length(a)>0 && length(b)>0,"H1 requires both vehicle types.")
    fit <- stats::wilcox.test(a,b,alternative="two.sided",exact=FALSE,correct=TRUE)
    u <- unname(fit$statistic); superiority <- u/(length(a)*length(b))
    row <- c(list(hypothesis="H1",sample=sample,status="computed",statistic_name="Mann-Whitney U (BEV)",statistic=u,
      n=nrow(z),n_bev=length(a),n_phev=length(b),p_method="asymptotic normal, ties and continuity corrected",alternative="two-sided"),
      ct_p(fit$p.value),list(effect_name="rank-biserial (BEV minus PHEV)",effect_size=2*superiority-1,
      probability_superiority_bev=superiority,effect_definition="2 * U_BEV / (n_BEV * n_PHEV) - 1"))
    for(type in c("bev","phev")) {
      v <- if(type=="bev") a else b; q <- quantile(v,c(.25,.5,.75),names=FALSE,type=7)
      row[[paste0(type,"_median_miles")]] <- q[2]; row[[paste0(type,"_q1_miles")]] <- q[1]
      row[[paste0(type,"_q3_miles")]] <- q[3]; row[[paste0(type,"_iqr_miles")]] <- q[3]-q[1]
    }
    rows[[length(rows)+1L]] <- row
  }
  paired <- x[x$h2_valid,]
  for(sample in c("all_valid","bev","phev")) {
    z <- if(sample=="all_valid") paired else paired[paired$vehicle_type==toupper(sample),]
    valid <- nrow(z)>=3 && length(unique(z$model_year))>1 && length(unique(z$electric_range))>1
    if(valid) {fit <- stats::cor.test(z$model_year,z$electric_range,method="spearman",exact=FALSE,continuity=FALSE);rho <- unname(fit$estimate);pr<-ct_p(fit$p.value)}
    else {rho<-NA_real_;pr<-list(p_value=NA_real_,p_display="not computed",p_numerical_underflow=FALSE,p_value_upper_bound=NA_real_,nominal_alpha=.05,reject_h0=NA)}
    rows[[length(rows)+1L]] <- c(list(hypothesis="H2",sample=sample,status=if(valid) "computed" else "undefined_constant_or_small_sample",statistic_name="Spearman rho",
      statistic=rho,n=nrow(z),p_method="asymptotic t approximation",alternative="two-sided"),pr,
      list(effect_name="Spearman rho",effect_size=rho,effect_definition="Spearman rank correlation between Model Year and Electric Range."))
  }
  groups <- unique(paired[c("vehicle_type","model_year")]); groups <- groups[order(groups$vehicle_type,groups$model_year),]
  year <- do.call(rbind,lapply(seq_len(nrow(groups)),function(i) {
    v <- paired$electric_range[paired$vehicle_type==groups$vehicle_type[i] & paired$model_year==groups$model_year[i]]
    q <- quantile(v,c(.25,.5,.75),names=FALSE,type=7)
    data.frame(vehicle_type=groups$vehicle_type[i],model_year=groups$model_year[i],valid_n=length(v),median_miles=q[2],q1_miles=q[1],q3_miles=q[3])
  }))
  list(range_tests.csv=ev_rbind(rows),range_year_summary.csv=year)
}
rg_main <- function() {
  a <- ev_cli(c("range-sample","output-dir","figures-dir"),"python-results-dir",
    "Rscript range_tests.R --range-sample FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]")
  if(is.null(a)) return(invisible(NULL))
  tables <- rg_build(rg_load(a[["range-sample"]])); z <- tables$range_year_summary.csv
  plots <- list(range_by_model_year.png=function() {
    plot(range(z$model_year),range(c(z$q1_miles,z$q3_miles)),type="n",xlab="Model year",ylab="Electric range (miles)",main="Electric range by model year: median and IQR")
    for(i in seq_along(c("BEV","PHEV"))) {w<-z[z$vehicle_type==c("BEV","PHEV")[i],]; col<-c("#087e8b","#e69f00")[i]
      polygon(c(w$model_year,rev(w$model_year)),c(w$q1_miles,rev(w$q3_miles)),col=adjustcolor(col,.2),border=NA);lines(w$model_year,w$median_miles,col=col,lwd=2)}
    legend("topleft",c("BEV","PHEV"),col=c("#087e8b","#e69f00"),lty=1,bty="n")
  })
  cols <- list(range_tests.csv=c("hypothesis","sample","statistic","n","p_value","p_numerical_underflow","reject_h0","effect_size"))
  checks <- ct_compare(tables,a[["python-results-dir"]],list(range_tests.csv=c("hypothesis","sample"),range_year_summary.csv=c("vehicle_type","model_year")),"range_tests.csv")
  ev_publish(tables,a[["output-dir"]],a[["figures-dir"]],plots,a[["range-sample"]],"range_tests",checks)
}

if (sys.nframe() == 0L) rg_main()
