# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Locate the sibling utility both under Rscript and when sourced interactively.
ct_path <- local({
  frames <- sys.frames(); files <- unlist(lapply(frames,function(f) f$ofile))
  if(length(files)) tail(files,1) else sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
})
if(is.na(ct_path) || !nzchar(ct_path)) stop("Source this script by its file path.",call.=FALSE)
source(file.path(dirname(normalizePath(ct_path,mustWork=TRUE)),"contingency.R"),local=TRUE)

# H3 vehicle type versus CAFV labels, parallel to cafv_test.py.
cf_labels <- c("Clean Alternative Fuel Vehicle Eligible","Not eligible due to low battery range","Eligibility unknown as battery range has not been researched")
cf_load <- function(path) {
  x <- ev_read(path,c("source_record","county","vehicle_type","cafv_status","cafv_known"));ct_records(x)
  ev_require(!anyNA(x$cafv_status) && all(x$cafv_status %in% cf_labels),"Unexpected CAFV label.")
  x$cafv_known <- ev_bool(x$cafv_known,"cafv_known")
  ev_require(all(x$cafv_known==(x$cafv_status!=cf_labels[3])),"CAFV known flag disagrees with label.");x
}
cf_main <- function() {
  a <- ev_cli(c("cafv-sample","output-dir","figures-dir"),"python-results-dir",
    "Rscript cafv_test.R --cafv-sample FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]")
  if(is.null(a)) return(invisible(NULL))
  x <- cf_load(a[["cafv-sample"]]); rows<-list(); cells<-list()
  for(sample in c("known_labels","including_unknown")) {
    z <- if(sample=="known_labels") x[x$cafv_known,] else x
    labels <- if(sample=="known_labels") cf_labels[1:2] else cf_labels
    tab <- table(factor(z$vehicle_type,levels=c("BEV","PHEV")),factor(z$cafv_status,levels=labels))
    fit <- ct_chisq(tab,"H3",sample)
    fit$row$n_bev <- sum(z$vehicle_type=="BEV");fit$row$n_phev<-sum(z$vehicle_type=="PHEV")
    fit$row$unknown_excluded <- sample=="known_labels"
    rows[[length(rows)+1L]]<-fit$row;cells[[length(cells)+1L]]<-fit$cells
  }
  tables<-list(cafv_tests.csv=ev_rbind(rows),cafv_contingency.csv=do.call(rbind,cells))
  plots<-list(cafv_by_vehicle_type.png=function() {
    tab<-table(factor(x$cafv_status,levels=cf_labels),factor(x$vehicle_type,levels=c("BEV","PHEV")))
    barplot(100*sweep(tab,2,colSums(tab),"/"),col=c("#087e8b","#e69f00","#999999"),ylim=c(0,125),ylab="Share within vehicle type (%)",main="CAFV labels by vehicle type")
    legend("top",c("Eligible","Not eligible","Unknown"),fill=c("#087e8b","#e69f00","#999999"),bty="n",horiz=TRUE,cex=.85)
  })
  cols<-list(cafv_tests.csv=c("hypothesis","sample","statistic","n","p_value","p_numerical_underflow","reject_h0","effect_size","expected_min","expected_cells_lt_5","expected_cells_lt_1","df_theoretical"))
  checks<-ct_compare(tables,a[["python-results-dir"]],list(cafv_tests.csv=c("hypothesis","sample"),cafv_contingency.csv=c("hypothesis","sample","row_label","column_label")),"cafv_tests.csv")
  ev_publish(tables,a[["output-dir"]],a[["figures-dir"]],plots,a[["cafv-sample"]],"cafv_test",checks)
}

if (sys.nframe() == 0L) cf_main()
