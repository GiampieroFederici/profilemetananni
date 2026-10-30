#!/usr/bin/env Rscript
# motore/multicampione.R - multi-sample statistics of PMN 1.1 (R11). ONE profiler per call: MetaPhlAn and Kraken are
# never merged. Inputs are written by motore/multicampione.py in --dir (the design and the choice of the tests are made
# there); outputs (TSV tables, PNG and PDF plots in English) go to the same folder. Conda env: pmn_stats_r.
#   Rscript multicampione.R --dir DIR [--seed 1992] [--permutations 999] [--profiler metaphlan|kraken]
# Inputs: abundance_relative.tsv (taxa x samples, closed to 1), alpha_diversity.tsv (equal depth), comparisons.tsv,
# design.tsv, parametri.tsv (rows are appended here: versions, zero replacement value, PCoA variance).
# Methods: Aitchison distance = Euclidean on CLR after multiplicative zero replacement (Martin-Fernandez et al. 2003,
# doi:10.1023/A:1023866030544; Gloor et al. 2017, doi:10.3389/fmicb.2017.02224); Bray-Curtis on relative abundances;
# PERMANOVA = vegan::adonis2 (Anderson 2001, doi:10.1111/j.1442-9993.2001.01070.pp.x) ALWAYS with PERMDISP =
# vegan::betadisper + permutest (Anderson 2006, doi:10.1111/j.1541-0420.2005.00440.x), on the same permutation set
# (permute::shuffleSet; blocks = subject for repeated measures). No F and no p when the statistic is not defined. A significant PERMANOVA with different dispersions
# may reflect dispersion, not location (Anderson & Walsh 2013, doi:10.1890/12-2010.1).
suppressPackageStartupMessages({library(vegan); library(permute); library(ggplot2)})

args <- commandArgs(trailingOnly = TRUE)
opt <- function(flag, default = NULL) {
  i <- which(args == flag)
  if (length(i) == 1 && i < length(args)) args[i + 1] else default
}
dir <- opt("--dir")
seed <- as.integer(opt("--seed", "1992"))
nperm <- as.integer(opt("--permutations", "999"))
profiler <- opt("--profiler", "")
if (is.null(dir) || !dir.exists(dir)) stop("usage: --dir DIR")
label <- unname(c(metaphlan = "MetaPhlAn", kraken = "Kraken + Bracken (prototype)")[profiler])
if (is.na(label)) label <- profiler
f <- function(x) file.path(dir, x)
tab <- function(x) read.delim(f(x), check.names = FALSE, stringsAsFactors = FALSE, colClasses = "character")
out <- function(df, x) write.table(df, f(x), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
fmt <- function(x, d = 3) ifelse(is.na(x), "", trimws(formatC(signif(as.numeric(x), d), format = "fg", digits = d)))
param <- list()
add_param <- function(k, v, note = "") param[[length(param) + 1]] <<- data.frame(parameter = k, value = v, note = note)

# ---------------- data ----------------
ab <- as.matrix(read.delim(f("abundance_relative.tsv"), row.names = 1, check.names = FALSE))
P <- t(ab)
P <- P / rowSums(P)                                   # samples x taxa, closed to 1
samples <- rownames(P)
n <- length(samples)
delta <- min(P[P > 0]) / 2                            # zero replacement value, declared in parametri.tsv
Z <- P == 0
X <- P * (1 - rowSums(Z) * delta)                     # multiplicative replacement: ratios of non-zero taxa unchanged
X[Z] <- delta
clr <- log(X) - rowMeans(log(X))
add_param("zero_replacement", formatC(delta, format = "g", digits = 4),
          "pseudocount for CLR: half of the smallest non-zero relative abundance, multiplicative replacement")
dist_of <- function(kind, M) if (kind == "aitchison") dist(M) else vegdist(M, "bray")
kinds <- c(aitchison = "Aitchison distance (CLR)", braycurtis = "Bray-Curtis dissimilarity")
dists <- list(aitchison = dist(clr), braycurtis = vegdist(P, "bray"))
for (k in names(kinds)) {
  out(data.frame(sample = samples, as.matrix(dists[[k]]), check.names = FALSE), paste0("distance_", k, ".tsv"))
}

pcoa <- function(d) {
  e <- tryCatch(suppressWarnings(cmdscale(d, k = min(2, n - 1), eig = TRUE)), error = function(e) NULL)
  pts <- if (is.null(e)) matrix(0, n, 2) else e$points
  if (is.null(dim(pts)) || ncol(pts) == 0) pts <- matrix(0, n, 2)
  if (ncol(pts) < 2) pts <- cbind(pts, 0)
  pos <- if (is.null(e)) 0 else sum(e$eig[e$eig > 0])
  pct <- if (pos > 0) 100 * pmax(e$eig[1:2], 0) / pos else c(0, 0)
  pct[is.na(pct)] <- 0
  list(points = data.frame(sample = samples, PCoA1 = pts[, 1], PCoA2 = pts[, 2]), pct = pct)
}
pcoas <- lapply(dists, pcoa)
for (k in names(kinds)) {
  out(pcoas[[k]]$points, paste0("pcoa_", k, ".tsv"))
  add_param(paste0("pcoa_", k, "_variance_pct"), paste(sprintf("%.1f", pcoas[[k]]$pct), collapse = "; "),
            "axis 1; axis 2 (share of the positive eigenvalues)")
}

alpha <- read.delim(f("alpha_diversity.tsv"), check.names = FALSE, stringsAsFactors = FALSE)
alpha$sample <- as.character(alpha$sample)
metrics <- c(richness = "Richness", shannon = "Shannon", simpson = "Simpson (1 - D)")
comps <- tab("comparisons.tsv")
design <- tab("design.tsv")

# ---------------- alpha diversity tests ----------------
r_from_p <- function(p, n) abs(qnorm(p / 2)) / sqrt(n)        # Fritz et al. 2012, doi:10.1037/a0024338
alpha_rows <- list()
post_rows <- list()
pairs_of <- function(pw, cmp, m, test) {                       # pairwise.wilcox.test matrix -> rows
  raw <- pw$raw
  adj <- pw$adj
  r <- list()
  for (i in rownames(adj)) for (j in colnames(adj)) if (!is.na(adj[i, j])) {
    r[[length(r) + 1]] <- data.frame(comparison = cmp, metric = m, test = test, group1 = j, group2 = i,
                                     statistic = "", p = fmt(raw[i, j], 4), p_adj = fmt(adj[i, j], 4))
  }
  do.call(rbind, r)
}
for (i in seq_len(nrow(comps))) {
  cmp <- comps[i, ]
  if (cmp$alpha_test == "none") next
  des <- design[design$comparison == cmp$comparison & design$alpha == "1", c("sample", "level", "unit")]
  a <- merge(des, alpha, by = "sample")
  a <- a[a$status != "not_equalized", ]
  if (cmp$design == "between_subjects") {        # the subject is the independent unit: mean of its samples
    a <- aggregate(a[names(metrics)], by = list(unit = a$unit, level = a$level), FUN = mean)
  }
  a <- a[order(a$level, a$unit), ]
  for (m in names(metrics)) {
    y <- a[[m]]
    g <- factor(a$level)
    row <- tryCatch(switch(cmp$alpha_test,
      mann_whitney = {
        t <- suppressWarnings(wilcox.test(y ~ g))
        list(n = length(y), sn = "W", s = t$statistic, p = t$p.value, en = "r", e = r_from_p(t$p.value, length(y)))
      },
      kruskal_dunn = {
        t <- kruskal.test(y ~ g)
        dn <- rstatix::dunn_test(data.frame(v = y, grp = g), v ~ grp, p.adjust.method = "BH")
        post_rows[[length(post_rows) + 1]] <- data.frame(comparison = cmp$comparison, metric = m, test = "Dunn",
          group1 = dn$group1, group2 = dn$group2, statistic = fmt(dn$statistic, 4), p = fmt(dn$p, 4),
          p_adj = fmt(dn$p.adj, 4))
        list(n = length(y), sn = "H", s = t$statistic, p = t$p.value, en = "epsilon2", e = t$statistic / (length(y) - 1))
      },
      wilcoxon_paired = {
        lv <- levels(g)
        x1 <- a[a$level == lv[1], ]
        x2 <- a[a$level == lv[2], ][match(x1$unit, a$unit[a$level == lv[2]]), ]
        t <- suppressWarnings(wilcox.test(x1[[m]], x2[[m]], paired = TRUE))
        list(n = nrow(x1), sn = "V", s = t$statistic, p = t$p.value, en = "r", e = r_from_p(t$p.value, nrow(x1)))
      },
      friedman = {
        t <- friedman.test(y ~ g | u, data = data.frame(y = y, g = g, u = factor(a$unit)))
        nb <- nlevels(factor(a$unit))
        pw <- list(raw = suppressWarnings(pairwise.wilcox.test(y, g, paired = TRUE, p.adjust.method = "none"))$p.value,
                   adj = suppressWarnings(pairwise.wilcox.test(y, g, paired = TRUE, p.adjust.method = "BH"))$p.value)
        post_rows[[length(post_rows) + 1]] <- pairs_of(pw, cmp$comparison, m, "Wilcoxon paired")
        list(n = nb, sn = "chi2", s = t$statistic, p = t$p.value, en = "kendall_w",
             e = t$statistic / (nb * (nlevels(g) - 1)))
      }), error = function(e) list(n = length(y), sn = "", s = NA, p = NA, en = "", e = NA, note = conditionMessage(e)))
    if (is.na(row$p) && is.null(row$note)) {           # e.g. the same richness in every sample
      row$note <- "all values are equal: no test possible"
      row$e <- NA
    }
    alpha_rows[[length(alpha_rows) + 1]] <- data.frame(comparison = cmp$comparison, metric = m, test = cmp$alpha_test,
      n = row$n, statistic_name = row$sn, statistic = fmt(row$s, 4), p = fmt(row$p, 4), effect_size_name = row$en,
      effect_size = fmt(row$e, 3), note = if (is.null(row$note)) "" else row$note)
  }
}
empty_alpha <- data.frame(comparison = character(), metric = character(), test = character(), n = character(),
                          statistic_name = character(), statistic = character(), p = character(),
                          effect_size_name = character(), effect_size = character(), note = character())
out(if (length(alpha_rows)) do.call(rbind, alpha_rows) else empty_alpha, "alpha_tests.tsv")
out(if (length(post_rows)) do.call(rbind, post_rows) else
      data.frame(comparison = character(), metric = character(), test = character(), group1 = character(),
                 group2 = character(), statistic = character(), p = character(), p_adj = character()),
    "alpha_posthoc.tsv")

# ---------------- beta diversity: PERMANOVA always with PERMDISP ----------------
NOTE_IDENTICAL <- "all samples are identical: no test possible"
NOTE_WITHIN_IDENTICAL <- "samples are identical within each group: the statistic is not defined, no test"
NOTE_ZERO_DISPERSION <- "dispersion is zero in every group: the statistic is not defined, no test"
NOTE_EQUAL_WITHIN <- "dispersion is the same within each group: the statistic is not defined, no test"
NOTE_FEW_DISP <- "too few samples for a reliable p value of the dispersion"
MIN_DISP <- 5                                                    # D197: independent units per group for a PERMDISP p
beta_rows <- list()
captions <- list()
for (i in seq_len(nrow(comps))) {
  cmp <- comps[i, ]
  if (cmp$permutations == "none" || ncol(P) < 2) next
  des <- design[design$comparison == cmp$comparison & design$beta == "1", c("sample", "level", "unit")]
  for (k in names(kinds)) {
    res <- tryCatch({
      if (cmp$permutations == "subject_mean") {
        M <- if (k == "aitchison") clr else P
        Mu <- apply(M[des$sample, , drop = FALSE], 2, function(col) tapply(col, des$unit, mean))
        d <- dist_of(k, Mu)
        g <- factor(des$level[match(rownames(Mu), des$unit)])
        h <- how(nperm = nperm)
      } else {
        idx <- match(des$sample, samples)
        d <- as.dist(as.matrix(dists[[k]])[idx, idx])
        g <- factor(des$level)
        h <- if (cmp$permutations == "blocks") how(nperm = nperm, blocks = factor(des$unit)) else how(nperm = nperm)
      }
      set.seed(seed)
      perms <- shuffleSet(attr(d, "Size"), control = h, quietly = TRUE)
      dm <- max(as.matrix(d))
      ad <- adonis2(d ~ g, data = data.frame(g = g), permutations = perms)
      # 30/10 (VM B2-5a): with (nearly) identical samples the residual or the dispersions are rounding noise and an F
      # from them is not a statistic: it gave PERMDISP p = 0.001 with 3 + 3 samples. Such cases get no p, only a note.
      a_note <- if (dm == 0 || ad$SumOfSqs[3] <= 1e-10 * dm^2) NOTE_IDENTICAL else
        if (ad$SumOfSqs[2] <= 1e-10 * ad$SumOfSqs[3]) NOTE_WITHIN_IDENTICAL else ""
      # PERMDISP: vegan::betadisper + permutest (permutation of residuals, Anderson 2006) on the same permutations.
      bd <- betadisper(d, g)
      z <- bd$distances
      ssw <- sum((z - ave(z, g))^2)
      # D197 (30/10): with fewer than MIN_DISP independent units in a group the residual-permutation p of permutest is
      # not calibrated (3 + 3 under a true null: 1.4 % below 0.05, all of them at p = 1/720): dispersions only.
      d_note <- if (dm == 0 || max(z) <= 1e-8 * dm) NOTE_ZERO_DISPERSION else
        if (ssw <= 1e-10 * dm^2 * length(z)) NOTE_EQUAL_WITHIN else
          if (min(table(g)) < MIN_DISP) NOTE_FEW_DISP else ""
      pt <- permutest(bd, permutations = perms)
      ok <- a_note == ""
      okd <- d_note == ""
      # smallest p the PERMANOVA can give with these permutations: the permutations that keep the same split count
      # as the observed one (with 3 + 3 and all 720 orders: 72/720 = 0.1)
      canon <- function(x) match(x, unique(x))
      same <- sum(apply(perms, 1, function(r) identical(canon(as.character(g[r])), canon(as.character(g)))))
      list(n = attr(d, "Size"), np = nrow(perms), adf = ad$Df[1], aF = if (ok) ad$F[1] else NA,
           aR2 = if (ok) ad$R2[1] else NA, ap = if (ok) ad[1, "Pr(>F)"] else NA, ddf = pt$tab$Df[1],
           dF = if (okd) pt$tab$F[1] else NA, dp = if (okd) pt$tab[1, "Pr(>F)"] else NA, note = c(a_note, d_note),
           pmin = (same + 1) / (nrow(perms) + 1),
           disp = paste(sprintf("%s: %s", levels(g), fmt(tapply(z, g, mean), 3)), collapse = "; "))
    }, error = function(e) list(n = nrow(des), np = NA, adf = NA, aF = NA, aR2 = NA, ap = NA, ddf = NA, dF = NA,
                                 dp = NA, note = rep(conditionMessage(e), 2), pmin = NA, disp = ""))
    differs <- !is.na(res$dp) && res$dp < 0.05
    beta_rows[[length(beta_rows) + 1]] <- data.frame(comparison = cmp$comparison, distance = k,
      test = c("PERMANOVA", "PERMDISP"), n = res$n, permutations = res$np, restriction = cmp$permutations,
      df = c(res$adf, res$ddf), F = fmt(c(res$aF, res$dF), 4), R2 = c(fmt(res$aR2, 3), ""),
      p = fmt(c(res$ap, res$dp), 3), dispersion_differs = c(if (is.na(res$dp)) "" else if (differs) "yes" else "no", ""),
      p_min = c(fmt(res$pmin, 3), ""), group_dispersion = c("", res$disp), note = res$note)
    captions[[paste(cmp$comparison, k)]] <- if (is.na(res$ap)) paste("No test:", res$note[1]) else paste0(
      "PERMANOVA R2 = ", fmt(res$aR2, 2), ", p = ", fmt(res$ap, 3), " (", res$np, " permutations, ",
      c(free = "free", blocks = "restricted within subject", subject_mean = "subject means")[cmp$permutations],
      "); ", if (is.na(res$dp)) paste("PERMDISP:", res$note[2]) else paste("PERMDISP p =", fmt(res$dp, 3)),
      if (differs) "\nDispersion differs between groups: PERMANOVA may reflect dispersion, not only location" else "")
  }
}
out(if (length(beta_rows)) do.call(rbind, beta_rows) else
      data.frame(comparison = character(), distance = character(), test = character(), n = character(),
                 permutations = character(), restriction = character(), df = character(), F = character(),
                 R2 = character(), p = character(), dispersion_differs = character(), p_min = character(),
                 group_dispersion = character(), note = character()),
    "beta_tests.tsv")

# ---------------- plots (English) ----------------
theme_set(theme_bw(base_size = 11))
save_plot <- function(p, name, w = 7.5, h = 5) {
  suppressWarnings(suppressMessages({
    ggsave(f(paste0(name, ".png")), p, width = w, height = h, dpi = 150)
    ggsave(f(paste0(name, ".pdf")), p, width = w, height = h)
  }))
}
long_alpha <- function(a) {
  do.call(rbind, lapply(names(metrics), function(m) data.frame(a[setdiff(names(a), names(metrics))],
                                                                 metric = metrics[[m]], value = a[[m]])))
}
along <- long_alpha(alpha[, c("sample", names(metrics))])
along$metric <- factor(along$metric, levels = metrics)
save_plot(ggplot(along, aes(sample, value)) + geom_point(size = 2.5) + facet_wrap(~metric, scales = "free_y") +
            labs(x = NULL, y = NULL, title = paste0(label, ": alpha diversity per sample (equal depth)")) +
            theme(axis.text.x = element_text(angle = 45, hjust = 1)), "alpha_samples", w = max(7.5, 0.25 * n + 4))
for (k in names(kinds)) {
  pc <- pcoas[[k]]
  p <- ggplot(pc$points, aes(PCoA1, PCoA2)) + geom_point(size = 2.5) +
    labs(x = sprintf("PCoA 1 (%.1f%%)", pc$pct[1]), y = sprintf("PCoA 2 (%.1f%%)", pc$pct[2]),
         title = paste0(label, ": PCoA, ", kinds[[k]]), caption = "No groups: descriptive only")
  if (n <= 40) p <- p + geom_text(aes(label = sample), size = 2.6, vjust = -0.9)
  save_plot(p, paste0("pcoa_", k))
}
for (i in seq_len(nrow(comps))) {
  cmp <- comps[i, ]
  des <- design[design$comparison == cmp$comparison, c("sample", "level", "unit")]
  within <- cmp$design %in% c("paired", "repeated")
  factor_name <- cmp$factor
  a <- merge(des, alpha, by = "sample")
  al <- long_alpha(a[, c("sample", "level", "unit", names(metrics))])
  al$metric <- factor(al$metric, levels = metrics)
  p <- ggplot(al, aes(level, value, colour = level)) + geom_boxplot(outlier.shape = NA, colour = "grey40") +
    facet_wrap(~metric, scales = "free_y") +
    labs(x = factor_name, y = NULL, colour = factor_name,
         title = paste0(label, ": alpha diversity by ", factor_name, " (equal depth)"),
         caption = paste("Test:", c(mann_whitney = "Mann-Whitney", kruskal_dunn = "Kruskal-Wallis + Dunn (BH)",
                                    wilcoxon_paired = "Wilcoxon signed-rank (paired)",
                                    friedman = "Friedman + paired Wilcoxon (BH)",
                                    none = "none (fewer than 3 units per group)")[cmp$alpha_test],
                         "- results in alpha_tests.tsv"))
  p <- if (within) p + geom_line(aes(group = unit), colour = "grey70") + geom_point(size = 2.2) else
    p + geom_jitter(width = 0.15, height = 0, size = 2.2)
  save_plot(p, paste0("alpha_", cmp$comparison))
  for (k in names(kinds)) {
    pc <- pcoas[[k]]
    df <- merge(pc$points, des, by = "sample")
    df <- df[order(df$unit, df$level), ]
    big <- names(which(table(df$level) >= 3))          # ellipses only with at least 3 samples per group
    p <- ggplot(df, aes(PCoA1, PCoA2, colour = level))
    if (within) p <- p + geom_path(aes(group = unit), colour = "grey70")
    if (length(big)) p <- p + stat_ellipse(data = df[df$level %in% big, ], type = "t", level = 0.95)
    p <- p + geom_point(size = 2.5) +
      labs(x = sprintf("PCoA 1 (%.1f%%)", pc$pct[1]), y = sprintf("PCoA 2 (%.1f%%)", pc$pct[2]), colour = factor_name,
           title = paste0(label, ": PCoA, ", kinds[[k]], ", by ", factor_name),
           caption = if (is.null(captions[[paste(cmp$comparison, k)]])) "No test: fewer than 3 units per group" else
             captions[[paste(cmp$comparison, k)]])
    save_plot(p, paste0("pcoa_", k, "_", cmp$comparison))
  }
}

# ---------------- versions ----------------
add_param("R", R.version.string)
for (pk in c("vegan", "permute", "ggplot2", "rstatix")) add_param(pk, as.character(packageVersion(pk)))
write.table(do.call(rbind, param), f("parametri.tsv"), sep = "\t", quote = FALSE, row.names = FALSE,
            col.names = FALSE, append = TRUE)
cat("[OK] multi-sample outputs in", dir, "\n")
