# -------------------------------------------------
#   Signal-to-Noise Ratio (SNR) Analysis
# -------------------------------------------------
# This script calculates the SNR for each sensor by comparing the average
# peak force during a press (Signal) to the standard deviation of the
# sensor's output when at rest (Noise).

# --- 1. Load necessary libraries ---
library(dplyr)
library(readr)
library(purrr)
library(stringr)
library(tidyr)

# --- 2. Set up paths ---
raw_data_folder <- "raw"
output_folder <- "Noise Analysis"

# Create the output directory if it doesn't exist
dir.create(output_folder, showWarnings = FALSE)

# --- 3. Find raw data files to process ---
if (!dir.exists(raw_data_folder)) {
    stop("Error: The 'raw' data folder was not found. Please create a 'raw' subfolder and place your original data CSVs inside it.")
}
csv_files <- list.files(path = raw_data_folder, pattern = "\\.csv$", full.names = TRUE)

if (length(csv_files) == 0) {
    stop("No raw data CSV files found in the 'raw' folder.")
}

cat("Found", length(csv_files), "raw data file(s) to process for SNR analysis...\n")

# --- 4. Loop through each file and collect intermediate results ---

# Use map_dfr to loop through files and row-bind the results into a single data frame
all_results <- map_dfr(csv_files, function(file_path) {
    file_basename <- tools::file_path_sans_ext(basename(file_path))
    cat("Processing:", basename(file_path), "\n")

    # --- Load and Harmonize Data ---
    df <- read_csv(file_path, col_types = cols(.default = col_character()), show_col_types = FALSE) %>%
        type_convert() %>%
        mutate(across(starts_with("fsr"), ~ . - 255.0)) # Apply offset

    # --- Calculate Noise (Standard Deviation of Baseline) for this file ---

    # Find all stimulus event times
    stim_times <- df %>%
        filter(tolower(event) == "stim" & !is.na(t_perf)) %>%
        pull(t_perf)

    # Create exclusion windows around each stimulus to isolate inter-trial intervals
    exclusion_windows <- tibble(start = stim_times - 0.2, end = stim_times + 1.5)

    # Filter for true baseline data (inter-trial intervals)
    baseline_data <- df %>%
        filter(is.na(event) | tolower(event) %in% c("", "sample")) %>%
        select(t_perf, starts_with("fsr")) %>%
        anti_join(exclusion_windows, by = join_by(t_perf >= start, t_perf <= end)) %>%
        filter(if_all(everything(), ~ !is.na(.)))

    # Calculate the standard deviation for each sensor's baseline
    noise_sd <- baseline_data %>%
        summarise(across(starts_with("fsr"), ~ sd(.x, na.rm = TRUE))) %>%
        pivot_longer(everything(), names_to = "sensor", values_to = "baseline_noise_sd")

    # --- Calculate Signal (Average Peak Force) for this file ---

    # Identify each stimulus event
    stim_events <- df %>%
        filter(tolower(event) == "stim" & !is.na(lane)) %>%
        mutate(trial_id = row_number()) %>%
        select(trial_id, t_perf, lane)

    # Extract the peak force for each stimulated trial
    peaks <- stim_events %>%
        group_by(trial_id) %>%
        do({
            this_trial <- .
            start_time <- this_trial$t_perf
            fsr_col <- paste0("fsr", this_trial$lane + 1)

            df_window <- df %>% filter(t_perf >= start_time, t_perf <= start_time + 1.2)
            peak_force <- max(df_window[[fsr_col]], na.rm = TRUE)

            tibble(lane = this_trial$lane, peak_force = peak_force)
        }) %>%
        ungroup()

    # Calculate the average peak force for each finger
    signal_avg <- peaks %>%
        group_by(lane) %>%
        summarise(avg_peak_signal = mean(peak_force, na.rm = TRUE)) %>%
        mutate(sensor = paste0("fsr", lane + 1)) %>% # Create a matching 'sensor' column
        select(sensor, avg_peak_signal)

    # Join the signal and noise tables for this file and return it
    signal_avg %>%
        left_join(noise_sd, by = "sensor")
})

# --- 5. Calculate Grand Average SNR across all files ---

grand_average_snr <- all_results %>%
    # Calculate the overall average signal and noise across all participants
    group_by(sensor) %>%
    summarise(
        grand_avg_signal = mean(avg_peak_signal, na.rm = TRUE),
        grand_avg_noise = mean(baseline_noise_sd, na.rm = TRUE),
        .groups = "drop"
    ) %>%
    # Calculate the final SNR from the grand averages
    mutate(grand_snr = grand_avg_signal / grand_avg_noise) %>%
    # Format for clarity
    mutate(sensor = str_replace(str_to_upper(sensor), "R", "")) %>%
    select(sensor, grand_avg_signal, grand_avg_noise, grand_snr)

# --- 6. Print and Save Final Result ---
cat("\n--- Grand Average SNR Across All Participants ---\n")
print(grand_average_snr)

summary_filename <- file.path(output_folder, "grand_average_snr_summary.csv")
write_csv(grand_average_snr, summary_filename)
cat("\nSuccessfully saved final summary to:", summary_filename, "\n")
