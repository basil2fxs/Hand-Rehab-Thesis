# -------------------------------------------------
# Repeatability of FSR Sensors (Stimulus-Response Based)
# -------------------------------------------------

library(dplyr)
library(ggplot2)
library(readr)
library(purrr)
library(stringr)

# --- 1. Set up paths ---
raw_data_folder <- "raw"
output_folder <- "repeat"

# Create the output directory if it doesn't exist
dir.create(output_folder, showWarnings = FALSE)

# --- 2. Find raw data files to process ---
if (!dir.exists(raw_data_folder)) {
    stop("Error: The 'raw' data folder was not found. Please create a 'raw' subfolder and place your original data CSVs inside it.")
}
csv_files <- list.files(path = raw_data_folder, pattern = "\\.csv$", full.names = TRUE)

if (length(csv_files) == 0) {
    stop("No raw data CSV files found in the 'raw' folder.")
}

cat("Found", length(csv_files), "raw data file(s) to process for repeatability analysis...\n")

# --- 3. Loop through each file, analyze, and plot ---

walk(csv_files, function(file_path) {
    file_basename <- tools::file_path_sans_ext(basename(file_path))
    cat("Processing:", basename(file_path), "\n")

    # --- Load and Harmonize Data ---
    df <- read_csv(file_path, col_types = cols(.default = col_character()), show_col_types = FALSE) %>%
        type_convert() %>%
        mutate(across(starts_with("fsr"), ~ . - 255.0)) # Apply offset

    # --- Identify Each Stimulus Event ---
    stim_events <- df %>%
        filter(tolower(event) == "stim" & !is.na(lane)) %>%
        mutate(trial_id = row_number()) %>%
        select(trial_id, t_perf, lane)

    # --- Extract Response Peaks for Each Stimulus ---
    peaks <- stim_events %>%
        group_by(trial_id) %>%
        do({
            this_trial <- .
            lane_num_0_indexed <- this_trial$lane
            start_time <- this_trial$t_perf

            df_window <- df %>%
                filter(t_perf >= start_time, t_perf <= start_time + 1.2)

            # Convert 0-indexed lane to 1-indexed finger for column name
            fsr_col <- paste0("fsr", lane_num_0_indexed + 1)
            peak_force <- max(df_window[[fsr_col]], na.rm = TRUE)

            tibble(
                trial_id = this_trial$trial_id,
                lane = lane_num_0_indexed,
                peak_force = peak_force
            )
        }) %>%
        ungroup()

    # --- Add segments (e.g., every 50 trials) for repeatability analysis ---
    peaks <- peaks %>%
        group_by(lane) %>%
        mutate(segment = ceiling(row_number() / 50)) %>%
        ungroup()

    # --- Summarise repeatability (mean, SD, CV%) ---
    repeat_stats <- peaks %>%
        group_by(lane, segment) %>%
        summarise(
            mean_force = mean(peak_force, na.rm = TRUE),
            sd_force = sd(peak_force, na.rm = TRUE),
            cv_percent = (sd_force / mean_force) * 100,
            .groups = "drop"
        )

    # --- Plot Repeatability ---
    p <- ggplot(repeat_stats, aes(x = segment, y = mean_force, color = factor(lane))) +
        geom_line(linewidth = 1) +
        geom_point(size = 2) +
        geom_errorbar(aes(ymin = mean_force - sd_force, ymax = mean_force + sd_force),
            width = 0.2, alpha = 0.6
        ) +
        labs(
            title = paste("FS Repeatability for:", file_basename),
            x = "Trial Segment (50 stim events each)",
            y = "Mean Peak Force (Corrected)",
            color = "Finger (Lane)"
        ) +
        theme_minimal(base_size = 14)

    # --- Save Outputs ---
    summary_filename <- file.path(output_folder, paste0("repeatability_summary_", file_basename, ".csv"))
    plot_filename <- file.path(output_folder, paste0("repeatability_plot_", file_basename, ".png"))

    write_csv(repeat_stats, summary_filename)
    ggsave(plot_filename, p, width = 10, height = 7, dpi = 150)

    cat(" -> Saved summary and plot to 'repeat' folder.\n")
    print(repeat_stats)
})

cat("\nAll repeatability analyses are complete.\n")
