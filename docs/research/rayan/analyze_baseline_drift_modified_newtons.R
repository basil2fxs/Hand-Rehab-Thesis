library(dplyr)
library(readr)
library(ggplot2)
library(purrr)
library(tidyr)
library(stringr)

# --- Paths ---
raw_data_folder        <- "raw"
output_baseline_folder <- "Stim Response Plots"
output_force_folder    <- "Force Analysis Plots"

dir.create(output_baseline_folder, showWarnings = FALSE)
dir.create(output_force_folder,    showWarnings = FALSE)

# --- Parameters ---
counts_per_newton <- 51.2
static_offset     <- 255.0
baseline_window   <- 50    # 250ms at 200Hz
sampling_rate     <- 200
fsr_cols          <- c("fsr1", "fsr2", "fsr3", "fsr4")

if (!dir.exists(raw_data_folder)) stop("Error: 'raw' folder not found.")
csv_files <- list.files(raw_data_folder, pattern = "\\.csv$", full.names = TRUE)

walk(csv_files, function(file_path) {

    file_basename <- tools::file_path_sans_ext(basename(file_path))
    cat("\n==========================================================\n")
    cat("Processing:", basename(file_path), "\n")
    cat("==========================================================\n")

    # Create session subfolders inside each output folder
    session_baseline_folder <- file.path(output_baseline_folder, file_basename)
    session_force_folder    <- file.path(output_force_folder,    file_basename)
    dir.create(session_baseline_folder, showWarnings = FALSE)
    dir.create(session_force_folder,    showWarnings = FALSE)

    # 1. Read Data
    raw_data <- read_csv(file_path, show_col_types = FALSE) %>%
        mutate(row_idx = row_number())

    if ("t_perf" %in% names(raw_data)) {
        raw_data <- raw_data %>% mutate(t_sec_raw = as.numeric(t_perf))
    } else {
        raw_data <- raw_data %>% mutate(t_sec_raw = row_idx / sampling_rate)
    }

    # 2. Identify Events
    processed_events_base <- raw_data %>%
        filter(!is.na(event)) %>%
        mutate(
            event_clean = tolower(trimws(event)),
            type = case_when(
                event_clean == "stim" ~ "Stim",
                str_detect(event_clean, "resp|press|response|key") ~ "Response",
                TRUE ~ NA_character_
            )
        ) %>%
        filter(!is.na(type))

    first_stim_time <- processed_events_base %>%
        filter(type == "Stim") %>%
        slice(1) %>%
        pull(t_sec_raw)
    if (length(first_stim_time) == 0) first_stim_time <- 0

    # Loop over each FSR sensor
    walk(fsr_cols, function(fsr_col) {

        if (!fsr_col %in% names(raw_data)) {
            cat("  -> Skipping", fsr_col, ": column not found.\n")
            return(invisible(NULL))
        }

        cat("\n--- Processing", toupper(fsr_col), "---\n")

        processed_events <- processed_events_base %>%
            mutate(
                fsr_raw  = raw_data[[fsr_col]][row_idx],
                fsr_corr = fsr_raw - static_offset,
                t_sec    = t_sec_raw - first_stim_time
            ) %>%
            rowwise() %>%
            mutate(
                start_idx       = max(1, row_idx - baseline_window),
                end_idx         = row_idx - 1,
                local_floor_raw = mean(raw_data[[fsr_col]][start_idx:end_idx], na.rm = TRUE),
                diff_counts     = fsr_raw - local_floor_raw,
                force_n_raw     = fsr_corr / counts_per_newton,
                force_n_zeroed  = (fsr_raw - local_floor_raw) / counts_per_newton
            ) %>%
            ungroup()

        responses_only <- processed_events %>% filter(type == "Response")

        cat(sprintf("%-10s | %-15s | %-12s | %-10s\n", "Time(s)", "Pre-Resp Base", "Raw Resp", "Diff(cts)"))
        cat("-----------|-----------------|--------------|-----------\n")
        pwalk(responses_only, function(t_sec, local_floor_raw, fsr_raw, diff_counts, ...) {
            cat(sprintf("%-10.2f | %-15.2f | %-12.0f | %-10.2f\n",
                        t_sec, local_floor_raw, fsr_raw, diff_counts))
        })

        avg_diff <- mean(responses_only$diff_counts, na.rm = TRUE)
        cat("----------------------------------------------------------\n")
        cat(sprintf("AVERAGE DIFF(cts) FOR SESSION (%s): %.2f\n", toupper(fsr_col), avg_diff))
        cat("----------------------------------------------------------\n")

        lm_raw  <- lm(force_n_raw    ~ t_sec, data = responses_only)
        lm_zero <- lm(force_n_zeroed ~ t_sec, data = responses_only)
        eq_raw  <- paste0("Raw: y = ",    round(coef(lm_raw)[2],  5), "x + ", round(coef(lm_raw)[1],  3))
        eq_zero <- paste0("Zeroed: y = ", round(coef(lm_zero)[2], 5), "x + ", round(coef(lm_zero)[1], 3))

        plot_data_n <- processed_events %>%
            select(t_sec, type, force_n_raw, force_n_zeroed) %>%
            pivot_longer(cols = c(force_n_raw, force_n_zeroed), names_to = "Method", values_to = "Force_N") %>%
            mutate(Method = ifelse(Method == "force_n_raw", "Raw (Static -255)", "Zeroed (250ms Baseline)"))

        y_breaks_n <- seq(-0.5, 4.0, by = 0.1)
        y_labels_n <- sapply(y_breaks_n, function(x) if (abs(x %% 0.5) < 0.01) format(x, nsmall = 1) else "")

        p_force <- ggplot(plot_data_n, aes(x = t_sec, y = Force_N, colour = type, linetype = Method)) +
            geom_hline(yintercept = 0, linetype = "dashed", colour = "grey40") +
            geom_line(linewidth = 0.6, alpha = 0.3) +
            geom_point(aes(alpha = Method, shape = type), size = 2.5) +
            geom_smooth(data = filter(plot_data_n, type == "Response"),
                        aes(group = Method, linetype = Method),
                        method = "lm", color = "#FFCC00", se = FALSE, linewidth = 1.2) +
            annotate("text", x = 0, y = 3.8, label = eq_raw,  hjust = 0, color = "black", fontface = "italic") +
            annotate("text", x = 0, y = 3.6, label = eq_zero, hjust = 0, color = "black", fontface = "bold") +
            scale_alpha_manual(values = c("Raw (Static -255)" = 0.35, "Zeroed (250ms Baseline)" = 1.0)) +
            scale_linetype_manual(values = c("Raw (Static -255)" = "dotted", "Zeroed (250ms Baseline)" = "solid")) +
            scale_y_continuous(breaks = y_breaks_n, labels = y_labels_n, minor_breaks = NULL, name = "Force (Newtons)") +
            coord_cartesian(ylim = c(-0.5, 4.0)) +
            scale_colour_manual(values = c("Stim" = "#1565C0", "Response" = "#C62828")) +
            labs(
                title    = paste("Force Analysis (250ms Look-Back) \u2014", toupper(fsr_col), "\u2014", file_basename),
                subtitle = "Yellow Lines = Trends | Zeroing window = 250ms (50 samples).",
                x        = "Time (s) from First Stim"
            ) +
            theme_minimal(base_size = 14) +
            theme(
                legend.position    = "bottom",
                panel.grid.major.y = element_line(colour = "grey92"),
                legend.box         = "vertical"
            )

        out_file <- file.path(session_force_folder, paste0("force_N_trends_", fsr_col, ".png"))
        ggsave(out_file, p_force, width = 16, height = 9, dpi = 300)
        cat("  -> Saved:", file.path(file_basename, basename(out_file)), "\n")
    })

    cat("\n")
})
