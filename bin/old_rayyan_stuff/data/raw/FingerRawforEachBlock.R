# R script to create trial-by-trial force plots for each participant.
#
# This script reads each processed CSV file, and for each file, it generates
# a single plot showing the peak force of all four fingers for every trial.
# It highlights the data point for the finger that was supposed to move.

# --- 1. Load necessary libraries ---
# If you don't have these installed, run: install.packages(c("dplyr", "readr", "ggplot2", "purrr", "tidyr", "stringr"))
library(dplyr)
library(readr)
library(ggplot2)
library(purrr)
library(tidyr)
library(stringr)

# --- 2. Set up paths ---
# The script assumes it's located in the "Data Analysis (R)" folder.
processed_data_folder <- "Processed Data"
output_plot_folder <- "Trial Plots"

# Check if the folder exists
if (!dir.exists(processed_data_folder)) {
    stop("Error: The '", processed_data_folder, "' folder was not found. Make sure you have run the Python script first.")
}

# Create the output directory for plots if it doesn't exist
dir.create(output_plot_folder, showWarnings = FALSE)

# --- 3. Get list of files to process ---
# Get a list of all CSV files in the directory
csv_files <- list.files(path = processed_data_folder, pattern = "processed_peaks_.*\\.csv$", full.names = TRUE)

if (length(csv_files) == 0) {
    stop("No processed CSV files found in the '", processed_data_folder, "' folder.")
}

# --- 4. Loop through each file, create and save a plot ---

cat("Found", length(csv_files), "file(s) to process. Generating plots...\n")

# --- Helper function to create a plot for a block of data ---
create_and_save_block_plot <- function(block_data, file_basename, block_identifier, block_subtitle) {
    if (nrow(block_data) == 0) {
        cat(" -> Skipping plot for", block_subtitle, "as no data was found.\n")
        return()
    }

    # Reshape data from 'wide' to 'long' format for plotting with ggplot
    long_data <- block_data %>%
        pivot_longer(
            cols = starts_with("peak_fsr"),
            names_to = "finger",
            values_to = "peak_force"
        ) %>%
        mutate(
            finger_num = as.integer(str_extract(finger, "\\d+")),
            is_stimulated = (finger_num == (stim_lane + 1))
        )

    # Create the plot
    p <- ggplot(long_data, aes(x = trial_id, y = peak_force)) +
        geom_line(aes(group = finger), color = "grey60") +
        geom_point(aes(size = is_stimulated, alpha = is_stimulated, color = finger)) +
        facet_wrap(~finger, ncol = 1, scales = "free_y") +
        scale_size_manual(values = c(`TRUE` = 3, `FALSE` = 1.5), guide = "none") +
        scale_alpha_manual(values = c(`TRUE` = 1.0, `FALSE` = 0.6), guide = "none") +
        scale_color_manual(
            values = c("peak_fsr1_raw" = "#E41A1C", "peak_fsr2_raw" = "#377EB8", "peak_fsr3_raw" = "#4DAF4A", "peak_fsr4_raw" = "#984EA3"),
            guide = "none"
        ) +
        labs(
            title = paste("Peak Force for:", file_basename),
            subtitle = paste(block_subtitle, "(Larger points indicate stimulated trials)"),
            x = "Trial ID",
            y = "Peak Raw Value (Corrected)"
        ) +
        theme_minimal(base_size = 12) +
        theme(
            plot.title = element_text(face = "bold", size = 14),
            strip.text = element_text(face = "bold", size = 12)
        )

    # Define the output filename
    output_filename <- file.path(
        output_plot_folder,
        paste0(file_basename, "_", block_identifier, ".png")
    )

    ggsave(output_filename, p, width = 12, height = 9, dpi = 150)
    cat(" -> Saved plot:", basename(output_filename), "\n")
}

# Use purrr::walk to iterate over each file
walk(csv_files, function(file_path) {
    # Read the single CSV file
    data <- read_csv(file_path, col_types = cols(.default = col_double(), reaction_time_ms = col_character()))

    # Reshape data from 'wide' to 'long' format for plotting with ggplot
    long_data <- data %>%
        filter(!is.na(trial_id))

    file_basename <- tools::file_path_sans_ext(basename(file_path))
    cat("Processing file:", basename(file_path), "\n")

    # Create plot for Block 1: First 50 trials
    create_and_save_block_plot(filter(long_data, trial_id >= 1 & trial_id <= 50), file_basename, "block1_random", "Trials 1-50")

    # Create plot for Block 2: Main 500 trials
    create_and_save_block_plot(filter(long_data, trial_id >= 51 & trial_id <= 550), file_basename, "block2_structured", "Trials 51-550")

    # Create plot for Block 3: Last 50 trials
    create_and_save_block_plot(filter(long_data, trial_id >= 551 & trial_id <= 600), file_basename, "block3_random_final", "Trials 551-600")
})

cat("\nAll plots have been saved to the 'Trial Plots' folder.\n")
