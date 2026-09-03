.libPaths(c("C:/Users/Rayyan/R/library", .libPaths()))

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(stringr)
  library(purrr)
  library(ggplot2)
  library(lmerTest)
  library(emmeans)
  library(pbkrtest)
  library(rstudioapi)
})

rm(list = ls())
options(scipen = 999)
cat("\014")

# -------- Settings -----------------------------------------------------------
enforce_five_blocks <- FALSE
rt_min <- 0
rt_max <- 1000

# -------- Output folder for plots --------------------------------------------
output_plot_folder <- "Analysis Plots"
dir.create(output_plot_folder, showWarnings = FALSE)

# -------- Read & Harmonise ---------------------------------------------------
get_script_path <- function() {
  if (interactive() && requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable()) {
    return(dirname(rstudioapi::getSourceEditorContext()$path))
  } else {
    cmd_args <- commandArgs(trailingOnly = FALSE)
    file_arg <- grep("--file=", cmd_args, value = TRUE)
    if (length(file_arg) == 1) {
      return(dirname(sub("--file=", "", file_arg)))
    } else {
      return(getwd())
    }
  }
}
data_folder <- get_script_path()

all_csvs <- list.files(pattern = "\\.csv$", full.names = TRUE)
sizes    <- file.info(all_csvs)$size
use_csvs <- all_csvs[sizes < 200 * 1024]
if (!length(use_csvs)) stop("No CSV files < 50 KB found in ", data_folder)
message("Reading ", length(use_csvs), " CSV(s):\n- ", paste(basename(use_csvs), collapse = "\n- "))

read_one <- function(path) {
  readr::read_csv(path, col_types = cols(.default = col_character()), show_col_types = FALSE) %>%
    mutate(source_file = basename(path))
}

raw <- map_dfr(use_csvs, read_one) %>% type_convert()
raw <- raw %>% mutate(block = dplyr::recode(block, aftertest = "posttest", .default = block))

# -------- De-duplicate while PRESERVING original FILE order ------------------
prefer_nonmiss_preserve <- function(df) {
  df <- df %>% mutate(
    row_idx      = dplyr::row_number(),
    early_late   = as.character(early_late),
    is_miss_flag = tolower(coalesce(early_late, "")) == "miss" |
      tolower(coalesce(error_type, "")) %in% c("miss", "timeout")
  )
  df %>%
    group_by(trial) %>%
    arrange(is_miss_flag, row_idx, .by_group = TRUE) %>%
    slice(1L) %>%
    ungroup() %>%
    arrange(row_idx) %>%
    select(-is_miss_flag)
}

Dat <- raw %>%
  group_by(source_file, participant, block) %>%
  group_modify(~ prefer_nonmiss_preserve(.x)) %>%
  ungroup()

# -------- Optional: enforce 5x100 main ---------------------------------------
if (enforce_five_blocks) {
  Dat <- Dat %>%
    group_by(source_file, participant, block) %>%
    mutate(row_in_group_tmp = row_number()) %>%
    filter(!(block == "main" & row_in_group_tmp > 500)) %>%
    select(-row_in_group_tmp) %>%
    ungroup()
}

# -------- Build block100 from ORIGINAL ORDER ---------------------------------
block100_map <- Dat %>%
  group_by(source_file, participant, block) %>%
  mutate(
    row_in_group = dplyr::row_number(),
    block100     = if_else(block == "main", as.integer(ceiling(row_in_group / 100)), 1L)
  ) %>%
  ungroup() %>%
  select(source_file, participant, block, trial, row_in_group, block100)

cat("\nBlock counts per file/participant:\n")
print(Dat %>% count(source_file, participant, block, name = "n"))

cat("\nMain block100 sizes (post-de-dup, pre-filters):\n")
print(block100_map %>% filter(block == "main") %>% count(source_file, participant, block100, name = "n"))

# -------- Exclusion flags ----------------------------------------------------
as_bool <- function(x) {
  if (is.logical(x)) return(x)
  lx <- tolower(as.character(x))
  dplyr::case_when(
    lx %in% c("true",  "t", "1", "yes", "y") ~ TRUE,
    lx %in% c("false", "f", "0", "no",  "n") ~ FALSE,
    TRUE ~ NA
  )
}

Dat <- Dat %>% mutate(
  had_incorrect_press = as_bool(had_incorrect_press),
  key_mismatch        = !is.na(keys_pressed) & !is.na(correct_keys) & keys_pressed != correct_keys,
  is_incorrect        = dplyr::coalesce(had_incorrect_press, FALSE) | key_mismatch,
  time_difference_ms  = as.numeric(time_difference_ms)
)

# -------- Analytic set -------------------------------------------------------
Analytic <- Dat %>%
  left_join(block100_map, by = c("source_file", "participant", "block", "trial")) %>%
  filter(
    !is.na(time_difference_ms),
    time_difference_ms >= rt_min,
    time_difference_ms <= rt_max,
    !is_incorrect
  ) %>%
  mutate(block_all = dplyr::case_when(
    block == "pretest"  ~ 0L,
    block == "main"     ~ pmax(1L, pmin(5L, as.integer(block100))),
    block == "posttest" ~ 6L,
    TRUE ~ NA_integer_
  )) %>%
  filter(!is.na(block_all)) %>%
  mutate(
    block_all_f = factor(block_all, levels = 0:6),
    participant = factor(participant),
    is_random   = block_all %in% c(0, 6)
  )

# -------- Diagnostics --------------------------------------------------------
n_participants <- nlevels(Analytic$participant)
cat("\nNumber of participants:", n_participants, "\n")
cat("Trials per block:\n")
print(Analytic %>% count(participant, block_all))

# -------- Plot 1: Distribution -----------------------------------------------
p_dist <- ggplot(Analytic, aes(x = block_all_f, y = time_difference_ms, fill = is_random)) +
  geom_violin(trim = FALSE, alpha = 0.6) +
  geom_boxplot(width = 0.15, outlier.shape = NA, alpha = 0.85, color = "black") +
  scale_fill_manual(
    values = c(`TRUE` = "firebrick", `FALSE` = "steelblue"),
    labels = c(`TRUE` = "Random (0,6)", `FALSE` = "Structured (1-5)"),
    name   = "Block type"
  ) +
  labs(
    title = "Distribution of Reaction Times Across Blocks (0-6)",
    x = "Block (0-6)", y = "Reaction Time (ms)"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    plot.title.position = "plot",
    plot.title   = element_text(face = "bold", hjust = 0),
    axis.title.x = element_text(margin = margin(t = 10)),
    axis.title.y = element_text(margin = margin(r = 10))
  )
print(p_dist)
ggsave(file.path(output_plot_folder, "plot_distribution.png"), p_dist, width = 12, height = 7, dpi = 300)
cat("-> Saved: plot_distribution.png\n")

# -------- Fit model: LMM if multiple participants, LM if single --------------
if (n_participants > 1) {
  cat("\nFitting Linear Mixed-Effects Model (multiple participants)...\n")
  m_all <- lmer(time_difference_ms ~ block_all_f + (1 | participant), data = Analytic)
} else {
  cat("\nOnly 1 participant found — fitting simple linear model (no random effects)...\n")
  m_all <- lm(time_difference_ms ~ block_all_f, data = Analytic)
}

emm_all   <- emmeans(m_all, ~block_all_f)
pairs_all <- contrast(emm_all, method = "pairwise", adjust = "holm")

# Planned contrast: post vs pre (only if all 7 blocks present)
n_blocks <- nrow(summary(emm_all))
if (n_blocks == 7) {
  c_post_vs_pre <- contrast(emm_all, list(post_vs_pre = c(-1, 0, 0, 0, 0, 0, 1)))
  cat("\nPost vs Pre contrast:\n")
  print(summary(c_post_vs_pre, infer = TRUE))
} else {
  cat("-> Skipping post vs pre contrast: only", n_blocks, "of 7 blocks present in data.\n")
}

# Linear trend across structured blocks 1..5 (only if those blocks exist)
struct_blocks <- as.character(0:6)[as.character(0:6) %in% as.character(levels(droplevels(Analytic$block_all_f)))]
if (all(c("1","2","3","4","5") %in% struct_blocks)) {
  emm_struct <- emmeans(m_all, ~block_all_f, at = list(block_all_f = factor(1:5, levels = 0:6)))
  lin_con    <- list(linear_1to5 = c(-2, -1, 0, 1, 2))
  cat("\nLinear trend across structured blocks 1-5:\n")
  print(summary(contrast(emm_struct, lin_con), infer = TRUE))
} else {
  cat("-> Skipping linear trend: not all structured blocks 1-5 present.\n")
}

# -------- Plot 2: Estimated means --------------------------------------------
emm_df <- as.data.frame(summary(emm_all, infer = TRUE, level = 0.95))

# Handle column names for lm vs lmer
if (!"lower.CL" %in% names(emm_df)) {
  emm_df <- emm_df %>% rename(lower.CL = asymp.LCL, upper.CL = asymp.UCL)
}

emm_df <- emm_df %>%
  rename(block = block_all_f, mean = emmean, lower = lower.CL, upper = upper.CL) %>%
  mutate(block_num = as.integer(as.character(block)), is_random = block_num %in% c(0, 6))

p_emm <- ggplot(emm_df, aes(x = block_num, y = mean, group = 1)) +
  geom_line() +
  geom_errorbar(aes(ymin = lower, ymax = upper, colour = is_random), width = 0.15, linewidth = 0.9) +
  geom_point(aes(colour = is_random), size = 3) +
  scale_x_continuous(breaks = 0:6) +
  scale_colour_manual(
    values = c(`TRUE` = "firebrick", `FALSE` = "steelblue"),
    labels = c(`TRUE` = "Random (0, 6)", `FALSE` = "Structured (1-5)"),
    name   = "Block type"
  ) +
  labs(
    title = "Estimated Means by Block (emmeans)",
    x = "Block (0-6)", y = "Estimated RT (ms)"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    plot.title.position = "plot",
    plot.title   = element_text(face = "bold", hjust = 0),
    axis.title.x = element_text(margin = margin(t = 10)),
    axis.title.y = element_text(margin = margin(r = 10))
  )
print(p_emm)
ggsave(file.path(output_plot_folder, "plot_estimated_means.png"), p_emm, width = 12, height = 7, dpi = 300)
cat("-> Saved: plot_estimated_means.png\n")

# -------- Plot 3: Spaghetti --------------------------------------------------
pt_means <- Analytic %>%
  dplyr::group_by(participant, block_all) %>%
  dplyr::summarise(meanRT = mean(time_difference_ms), .groups = "drop")

grp_means <- pt_means %>%
  dplyr::group_by(block_all) %>%
  dplyr::summarise(
    mean = mean(meanRT),
    se   = if (dplyr::n() > 1) sd(meanRT) / sqrt(dplyr::n()) else 0,
    .groups = "drop"
  ) %>%
  dplyr::mutate(is_random = block_all %in% c(0, 6))

p_spaghetti <- ggplot() +
  geom_line(
    data = pt_means, aes(x = block_all, y = meanRT, group = participant),
    linewidth = 0.5, alpha = 0.4, colour = "grey70"
  ) +
  geom_line(data = grp_means, aes(x = block_all, y = mean, group = 1), colour = "black") +
  geom_errorbar(
    data = grp_means,
    aes(x = block_all, ymin = mean - se, ymax = mean + se, colour = is_random),
    width = 0.15, linewidth = 0.9
  ) +
  geom_point(data = grp_means, aes(x = block_all, y = mean, colour = is_random), size = 3) +
  scale_x_continuous(breaks = 0:6) +
  scale_colour_manual(
    values = c(`TRUE` = "firebrick", `FALSE` = "steelblue"),
    labels = c(`TRUE` = "Random (0, 6)", `FALSE` = "Structured (1-5)"),
    name   = "Block type"
  ) +
  labs(
    title = "Individual Learning Curves with Group Mean (Raw RT)",
    x = "Block (0-6)", y = "Mean RT per Participant (ms)"
  ) +
  theme_minimal(base_size = 14) +
  theme(
    plot.title.position = "plot",
    plot.title   = element_text(face = "bold", hjust = 0),
    axis.title.x = element_text(margin = margin(t = 10)),
    axis.title.y = element_text(margin = margin(r = 10))
  )
print(p_spaghetti)
ggsave(file.path(output_plot_folder, "plot_spaghetti.png"), p_spaghetti, width = 12, height = 7, dpi = 300)
cat("-> Saved: plot_spaghetti.png\n")

cat("\nAll plots saved to '", output_plot_folder, "/' folder.\n", sep = "")

# -------- Commented out: Save Statistical Results to CSV ---------------------
# output_data_folder <- "Report Data"
# dir.create(output_data_folder, showWarnings = FALSE)
#
# emm_tbl <- as.data.frame(summary(emm_all))
# write.csv(emm_tbl, file.path(output_data_folder, "estimated_means.csv"), row.names = FALSE)
#
# pairs_tbl <- as.data.frame(summary(pairs_all))
# write.csv(pairs_tbl, file.path(output_data_folder, "pairwise_comparisons.csv"), row.names = FALSE)
#
# if (n_blocks == 7) {
#   c_post_vs_pre_tbl <- as.data.frame(summary(c_post_vs_pre, infer = TRUE))
#   write.csv(c_post_vs_pre_tbl, file.path(output_data_folder, "contrast_pre_vs_post.csv"), row.names = FALSE)
# }
#
# if (all(c("1","2","3","4","5") %in% struct_blocks)) {
#   lin_con_tbl <- as.data.frame(summary(contrast(emm_struct, lin_con), infer = TRUE))
#   write.csv(lin_con_tbl, file.path(output_data_folder, "contrast_learning_trend.csv"), row.names = FALSE)
# }
#
# message("\nSuccessfully saved summary CSV files to the 'Report Data' folder.")

# -------- END ----------------------------------------------------------------
