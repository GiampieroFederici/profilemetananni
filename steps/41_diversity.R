#!/usr/bin/env Rscript
# steps/41_diversity.R - compositional diversity: CLR + Aitchison + PCA (beta) and alpha diversity.
# Conda env: pmn_stats_r (r-base, r-vegan, r-rstatix).
# Rationale: microbiome data are compositional; the Aitchison distance (Euclidean on CLR)
# is more stable than Bray-Curtis and is a true linear distance (Gloor et al. 2017,
# Front. Microbiol., DOI 10.3389/fmicb.2017.02224).
# Group tests on alpha diversity (only when --group-col is given): Kruskal-Wallis
# (Kruskal & Wallis 1952, JASA 47:583-621) + Dunn post-hoc, BH-adjusted
# (Dunn 1964, Technometrics 6:241-252; via the rstatix package).
#
# Usage:
#   Rscript 41_diversity.R --matrix MATRIX.tsv --out DIR [--metadata META.tsv --group-col COL]
# MATRIX.tsv = taxa (rows) x samples (cols), relative abundances.

suppressMessages(suppressWarnings(library(vegan)))

args <- commandArgs(trailingOnly = TRUE)
getopt <- function(flag, default = NULL) {
  i <- which(args == flag)
  if (length(i) == 1 && i < length(args)) args[i + 1] else default
}

mat_path  <- getopt("--matrix")
out_dir   <- getopt("--out")
meta_path <- getopt("--metadata", NA)
group_col <- getopt("--group-col", NA)

if (is.null(mat_path) || is.null(out_dir)) {
  stop("usage: --matrix FILE --out DIR [--metadata FILE --group-col COL]")
}
if (!file.exists(mat_path)) stop(paste("matrix not found:", mat_path))
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# --- read matrix (taxa x samples) and transpose to samples x taxa ---
m <- as.matrix(read.delim(mat_path, row.names = 1, check.names = FALSE))
mode(m) <- "numeric"
m[is.na(m)] <- 0
X <- t(m)                                  # samples x taxa
X <- X[, colSums(X) > 0, drop = FALSE]     # drop all-zero taxa
if (nrow(X) < 2) stop("need at least 2 samples for diversity analysis")
if (ncol(X) < 1) { message("[SKIP] no non-zero taxa in matrix"); quit(save = "no", status = 0) }

# --- CLR transform; pseudocount = half the minimum positive value ---
pos <- X[X > 0]
pc  <- if (length(pos) > 0) min(pos) / 2 else 1e-6
Xp  <- X + pc
# Vectorized CLR that ALWAYS keeps the matrix shape (samples x taxa). The old
# t(apply(Xp, 1, ...)) collapsed the sample axis when there was a single taxon,
# silently turning N samples into 1 phantom sample.
gm  <- exp(rowMeans(log(Xp)))
clr <- log(Xp / gm)

# --- Aitchison distance = Euclidean distance on CLR ---
ait <- dist(clr, method = "euclidean")
write.csv(as.matrix(ait), file.path(out_dir, "aitchison_distance.csv"))

# --- PCA on CLR ---
pca <- prcomp(clr, center = TRUE, scale. = FALSE)
ve  <- (pca$sdev^2) / sum(pca$sdev^2)
ve[!is.finite(ve)] <- 0                                     # degenerate PCA -> 0% (avoid NaN axis labels)
ncp <- min(2, ncol(pca$x))
scores <- as.data.frame(pca$x[, 1:ncp, drop = FALSE])
if (ncol(scores) < 2) scores$PC2 <- 0                       # degenerate (single taxon): keep plot/CSV valid
if (length(ve) < 2) ve <- c(ve, rep(0, 2 - length(ve)))
write.csv(scores, file.path(out_dir, "pca_scores.csv"))

# --- alpha diversity (on the original relative abundances) ---
# vegan::diversity() drops a single-column matrix to a vector and then pools every
# sample into one community; handle that case explicitly (a single taxon => 0 diversity).
if (ncol(X) == 1) {
  sh <- rep(0, nrow(X)); si <- rep(0, nrow(X))
} else {
  sh <- vegan::diversity(X, index = "shannon")
  si <- vegan::diversity(X, index = "simpson")
}
alpha <- data.frame(
  sample   = rownames(X),
  richness = rowSums(X > 0),
  shannon  = sh,
  simpson  = si,
  row.names = NULL
)

# --- optional grouping: colour PCA + Kruskal-Wallis on alpha ---
groups <- NULL
if (!is.na(meta_path) && !is.na(group_col) && file.exists(meta_path)) {
  meta <- read.delim(meta_path, check.names = FALSE, stringsAsFactors = FALSE)
  id_col <- if ("sample" %in% colnames(meta)) "sample" else colnames(meta)[1]
  if (group_col %in% colnames(meta) && anyDuplicated(meta[[id_col]])) {
    message("[WARN] duplicate sample IDs in metadata -> skipping grouping")
  } else if (group_col %in% colnames(meta)) {
    rownames(meta) <- as.character(meta[[id_col]])
    groups <- meta[rownames(X), group_col]
    if (all(is.na(groups))) {                 # no metadata IDs match the matrix samples
      message("[WARN] no metadata IDs match the matrix -> ungrouped")
      groups <- NULL
    } else {
      alpha[[group_col]] <- groups
    }
    # Kruskal-Wallis (global) per alpha metric, when there are >= 2 groups
    if (length(unique(na.omit(groups))) >= 2) {
      kw <- data.frame(
        metric = c("richness", "shannon", "simpson"),
        kruskal_p = c(
          tryCatch(kruskal.test(alpha$richness ~ as.factor(groups))$p.value, error = function(e) NA),
          tryCatch(kruskal.test(alpha$shannon  ~ as.factor(groups))$p.value, error = function(e) NA),
          tryCatch(kruskal.test(alpha$simpson  ~ as.factor(groups))$p.value, error = function(e) NA)
        )
      )
      write.csv(kw, file.path(out_dir, "alpha_kruskal.csv"), row.names = FALSE)

      # Dunn post-hoc (pairwise, BH-adjusted) per metric (Dunn 1964); needs rstatix.
      if (requireNamespace("rstatix", quietly = TRUE)) {
        dunn_rows <- list()
        for (mt in c("richness", "shannon", "simpson")) {
          dd <- data.frame(value = alpha[[mt]], grp = as.factor(groups))
          dd <- dd[!is.na(dd$grp), , drop = FALSE]
          res <- tryCatch(rstatix::dunn_test(dd, value ~ grp, p.adjust.method = "BH"),
                          error = function(e) NULL)
          if (!is.null(res) && nrow(res) > 0) {
            dunn_rows[[mt]] <- data.frame(
              metric = mt, group1 = res$group1, group2 = res$group2,
              statistic = res$statistic, p = res$p, p_adj = res$p.adj
            )
          }
        }
        if (length(dunn_rows) > 0) {
          write.csv(do.call(rbind, dunn_rows), file.path(out_dir, "alpha_dunn.csv"), row.names = FALSE)
        }
      } else {
        message("[WARN] package 'rstatix' not available -> skipping Dunn post-hoc")
      }
    }
  }
}
write.csv(alpha, file.path(out_dir, "alpha_diversity.csv"), row.names = FALSE)

# --- PCA plot (Aitchison) ---
png(file.path(out_dir, "pca_aitchison.png"), width = 1200, height = 1000, res = 150)
if (!is.null(groups)) {
  g  <- as.factor(groups)
  cols <- rainbow(length(levels(g)))[as.integer(g)]
  plot(scores[, 1], scores[, 2], col = cols, pch = 19,
       xlab = sprintf("PC1 (%.1f%%)", 100 * ve[1]),
       ylab = sprintf("PC2 (%.1f%%)", 100 * ve[2]),
       main = "PCA on CLR (Aitchison distance)")
  legend("topright", legend = levels(g), col = rainbow(length(levels(g))), pch = 19, bty = "n")
} else {
  plot(scores[, 1], scores[, 2], pch = 19,
       xlab = sprintf("PC1 (%.1f%%)", 100 * ve[1]),
       ylab = sprintf("PC2 (%.1f%%)", 100 * ve[2]),
       main = "PCA on CLR (Aitchison distance)")
}
invisible(dev.off())

cat("[OK] diversity outputs written to", out_dir, "\n")
