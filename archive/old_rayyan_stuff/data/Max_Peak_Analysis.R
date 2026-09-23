# -------------------------------------------------
#   Maximum & Average Peak Force Analysis
# -------------------------------------------------
# This script finds the peak force for every stimulated trial and then
# calculates the overall maximum and average peak force for each sensor
# across all participants.

# --- 1. Load necessary libraries ---
library(dplyr)
library(readr)
library(purrr)
library(stringr)

# --- 2. Set up paths ---
raw_data_folder <- "raw"
output_folder <- "Peak Analysis"

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

cat("Found", length(csv_files), "raw data file(s) to process for peak analysis...\n")

# --- 4. Loop through each file and extract all peak forces ---

# Use map_dfr to loop through files and row-bind the results into a single data frame
all_peaks <- map_dfr(csv_files, function(file_path) {
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

    if (nrow(stim_events) == 0) {
        cat(" -> No stimulus rows found. Skipping file.\n")
        return(NULL)
    }

    # --- Extract Response Peaks for Each Stimulus ---
    peaks_df <- stim_events %>%
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
                finger = lane_num_0_indexed + 1,
                peak_force = peak_force
            )
        }) %>%
        ungroup()

    return(peaks_df)
})

# --- 5. Calculate Overall Max and Average Peak Force ---

peak_summary <- all_peaks %>%
    group_by(finger) %>%
    summarise(
        overall_max_peak = max(peak_force, na.rm = TRUE),
        overall_avg_peak = mean(peak_force, na.rm = TRUE),
        n_presses = n(),
        .groups = "drop"
    ) %>%
    mutate(sensor = paste0("FS", finger)) %>%
    select(sensor, overall_max_peak, overall_avg_peak, n_presses)

# --- 6. Print and Save Final Result ---
cat("\n--- Overall Peak Force Summary Across All Participants ---\n")
print(peak_summary)

summary_filename <- file.path(output_folder, "overall_peak_force_summary.csv")
write_csv(peak_summary, summary_filename)
cat("\nSuccessfully saved final summary to:", summary_filename, "\n")
