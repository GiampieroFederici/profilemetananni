# MULTI: type I error of PERMANOVA and PERMDISP with 3 + 3 samples under a TRUE null hypothesis.
# Usage: Rscript multi_tipo1.R ABUNDANCE.tsv N_READS N_SIM OUT.tsv
# (1) the 10 distinct 3+3 splits of the 6 real profiles; (2) N_SIM null data sets: 6 samples drawn as multinomial
# read subsets (N_READS marker reads each) of the pooled real profile, split 3+3 (also 5+5 and 10+10 for context).
# PERMDISP p three ways: vegan::permutest (residual permutation), group-label permutation of the distances,
# parametric anova(betadisper). Same 999 permutation set as the PERMANOVA (seed 1992), as in motore/multicampione.R.
suppressPackageStartupMessages({library(vegan); library(permute)})
a <- commandArgs(TRUE)
ab <- as.matrix(read.delim(a[1], row.names = 1, check.names = FALSE))
P <- t(ab); P <- P / rowSums(P)
NR <- as.integer(a[2]); NS <- as.integer(a[3])
aitch <- function(P) { delta <- min(P[P > 0]) / 2; Z <- P == 0; X <- P * (1 - rowSums(Z) * delta); X[Z] <- delta
  dist(log(X) - rowMeans(log(X))) }
fan <- function(z, g) { m <- ave(z, g); k <- nlevels(g); (sum((m - mean(z))^2) / (k - 1)) / (sum((z - m)^2) / (length(z) - k)) }
PERMS <- list()
for (n in c(6, 10, 20)) {   # the same permutation set for every data set of size n (seed 1992, as in the engine)
  set.seed(1992); PERMS[[as.character(n)]] <- shuffleSet(n, control = how(nperm = 999), quietly = TRUE)
}
prove <- function(P, g) {
  n <- nrow(P)
  perms <- PERMS[[as.character(n)]]   # no set.seed here: it would reset the simulation stream (first run bug)
  out <- c()
  for (k in c("aitchison", "braycurtis")) {
    d <- if (k == "aitchison") aitch(P) else vegdist(P, "bray")
    ad <- adonis2(d ~ g, data = data.frame(g = g), permutations = perms)
    bd <- betadisper(d, g)
    pr <- permutest(bd, permutations = perms)$tab[1, "Pr(>F)"]
    z <- bd$distances; F0 <- fan(z, g)
    pl <- (sum(apply(perms, 1, function(i) fan(z, g[i])) >= F0 - sqrt(.Machine$double.eps)) + 1) / (nrow(perms) + 1)
    pp <- anova(bd)[1, "Pr(>F)"]
    out <- c(out, setNames(c(ad[1, "Pr(>F)"], pr, pl, pp),
                           paste(k, c("permanova", "permdisp_residui", "permdisp_etichette", "permdisp_parametrico"), sep = "_")))
  }
  out
}
righe <- list()
# (1) real profiles, all 10 distinct splits
cmb <- combn(6, 3)
cmb <- cmb[, cmb[1, ] == 1, drop = FALSE]          # 1 always in group A: 10 distinct splits
for (j in seq_len(ncol(cmb))) {
  g <- factor(ifelse(1:6 %in% cmb[, j], "A", "B"))
  righe[[length(righe) + 1]] <- c(dati = "reali", n_per_gruppo = 3, replica = j, prove(P, g))
}
# (2) simulated null: multinomial read subsets of the pooled profile
pool <- colMeans(P)
set.seed(20261030)
for (npg in c(3, 5, 10)) {
  nsim <- if (npg == 3) NS else max(100, NS %/% 5)
  for (s in seq_len(nsim)) {
    C <- t(rmultinom(2 * npg, NR, pool))
    C <- C[, colSums(C) > 0, drop = FALSE]
    Q <- C / rowSums(C)
    g <- factor(rep(c("A", "B"), each = npg))
    righe[[length(righe) + 1]] <- c(dati = "simulati", n_per_gruppo = npg, replica = s, prove(Q, g))
  }
}
res <- as.data.frame(do.call(rbind, righe), stringsAsFactors = FALSE)
write.table(res, a[4], sep = "\t", quote = FALSE, row.names = FALSE)
num <- grep("_", names(res), value = TRUE)
num <- setdiff(num, "n_per_gruppo")
for (k in num) res[[k]] <- as.numeric(res[[k]])
cat("\nType I error (share of p < 0.05)\n")
agg <- aggregate(res[num], by = list(dati = res$dati, n = res$n_per_gruppo), FUN = function(p) mean(p < 0.05))
nn <- aggregate(res$replica, by = list(dati = res$dati, n = res$n_per_gruppo), FUN = length)
agg$repliche <- nn$x
print(t(agg))
cat("\nmin p\n"); print(t(aggregate(res[num], by = list(dati = res$dati, n = res$n_per_gruppo), FUN = min)))
