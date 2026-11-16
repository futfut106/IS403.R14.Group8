# Preserve Vietnamese Windows paths when the inherited locale is not UTF-8.
if (.Platform$OS.type == "windows" && !l10n_info()[["UTF-8"]]) invisible(Sys.setlocale("LC_CTYPE", ".UTF-8"))
# Locate the sibling utility both under Rscript and when sourced interactively.
ct_path <- local({
  frames <- sys.frames(); files <- unlist(lapply(frames,function(f) f$ofile))
  if(length(files)) tail(files,1) else sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
})
if(is.na(ct_path) || !nzchar(ct_path)) stop("Source this script by its file path.",call.=FALSE)
source(file.path(dirname(normalizePath(ct_path,mustWork=TRUE)),"contingency.R"),local=TRUE)

# H4a composition and H4b penetration, parallel to county_tests.py.
co_load <- function(path,snapshots) {
  x<-ev_read(path,c("county","bev","phev","ev_total","included_h4a_sensitivity"))
  ev_require(!anyNA(x$county) && !anyDuplicated(x$county) && nrow(x)==39,"Expected 39 unique counties.")
  ev_numeric(x,c("bev","phev","ev_total"),counts=TRUE)
  ev_require(all(x$ev_total>0 & x$bev+x$phev==x$ev_total),"Invalid county EV counts.")
  x$included_h4a_sensitivity<-ev_bool(x$included_h4a_sensitivity,"included_h4a_sensitivity")
  ev_require(all(x$included_h4a_sensitivity==(x$ev_total>=30)),"County sensitivity flag disagrees with counts.")
  s<-ev_read(snapshots,c("date","county","bev","phev","ev_total","non_ev","total_vehicles","ev_pct"))
  ev_numeric(s,c("bev","phev","ev_total","non_ev","total_vehicles"),counts=TRUE);ev_numeric(s,"ev_pct")
  ev_require(nrow(s)==78 && !anyNA(s) && !anyDuplicated(s[c("date","county")]) && setequal(s$date,c("2017-01-31","2023-11-30")),"Expected two complete county snapshots.")
  for(date in unique(s$date)) ev_require(setequal(s$county[s$date==date],x$county),"Snapshot county coverage differs.")
  ev_require(all(s$bev+s$phev==s$ev_total & s$ev_total+s$non_ev==s$total_vehicles & s$total_vehicles>0) && all(abs(s$ev_pct-100*s$ev_total/s$total_vehicles)<1e-9),"Invalid snapshot counts/rates.")
  list(counts=x[order(x$county),],snapshots=s)
}
co_main <- function() {
  a<-ev_cli(c("county-counts","county-snapshots","output-dir","figures-dir"),"python-results-dir",
    "Rscript county_tests.R --county-counts FILE --county-snapshots FILE --output-dir DIR --figures-dir DIR [--python-results-dir DIR]")
  if(is.null(a)) return(invisible(NULL))
  data<-co_load(a[["county-counts"]],a[["county-snapshots"]]); x<-data$counts;s<-data$snapshots
  rows<-list();cells<-list()
  for(sample in c("all_counties","county_ev_ge_30")) {
    z<-if(sample=="all_counties") x else x[x$included_h4a_sensitivity,]
    tab<-as.matrix(z[c("bev","phev")]);rownames(tab)<-z$county
    fit<-ct_chisq(tab,"H4a",sample,force_monte_carlo=sample=="all_counties")
    fit$row$counties<-nrow(z);excluded<-sort(setdiff(x$county,z$county));fit$row$excluded_counties<-if(length(excluded)) paste(excluded,collapse="; ") else NA_character_
    rows[[length(rows)+1L]]<-fit$row;cells[[length(cells)+1L]]<-fit$cells
  }
  for(sample in c("latest_month","first_month")) {
    date<-if(sample=="latest_month") "2023-11-30" else "2017-01-31"
    z<-s[s$date==date,];z<-z[order(z$county),];tab<-as.matrix(z[c("ev_total","non_ev")]);rownames(tab)<-z$county
    fit<-ct_chisq(tab,"H4b",sample);fit$row$date<-date;fit$row$counties<-nrow(z);fit$row$excluded_counties<-NA_character_
    fit$cells$date<-date;rows[[length(rows)+1L]]<-fit$row;cells[[length(cells)+1L]]<-fit$cells
  }
  tables<-list(county_tests.csv=ev_rbind(rows),county_contingency.csv=ev_rbind(cells))
  plots<-list(county_vehicle_type_share.png=function() {
    par(mar=c(9,5,4,2),las=2)
    barplot(t(100*as.matrix(x[c("bev","phev")])/x$ev_total),names.arg=x$county,col=c("#087e8b","#e69f00"),cex.names=.65,ylim=c(0,115),ylab="Share (%)",main="BEV and PHEV composition within counties")
    legend("top",c("BEV","PHEV"),fill=c("#087e8b","#e69f00"),bty="n",horiz=TRUE)
  })
  # MC uses R's own RNG; exact simulated draws are not compared with NumPy.
  cols<-list(county_tests.csv=c("hypothesis","sample","statistic","n","p_numerical_underflow","reject_h0","effect_size","expected_min","expected_cells_lt_5","expected_cells_lt_1","df_theoretical","mc_resamples","mc_seed","mc_resolution"))
  checks<-ct_compare(tables,a[["python-results-dir"]],list(county_tests.csv=c("hypothesis","sample"),county_contingency.csv=c("hypothesis","sample","row_label","column_label")),"county_tests.csv")
  ev_publish(tables,a[["output-dir"]],a[["figures-dir"]],plots,c(a[["county-counts"]],a[["county-snapshots"]]),"county_tests",checks)
}

if (sys.nframe() == 0L) co_main()
