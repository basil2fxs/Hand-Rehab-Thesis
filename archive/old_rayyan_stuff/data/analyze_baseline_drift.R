library(dplyr)
library(readr)
library(ggplot2)
library(purrr)
library(tidyr)
library(stringr)

# --- Paths ---
raw_data_folder    <- "raw"
output_zoom_folder <- "Response_Waveforms"
dir.create(output_zoom_folder, showWarnings = FALSE)

# --- Parameters ---
sampling_rate  <- 200
pre_stim_s     <- 0.5
post_stim_s    <- 0.5
num_trials     <- 5    
ms_offsets     <- seq(50, 400, by = 50)
fsr_cols       <- c("fsr1", "fsr2", "fsr3", "fsr4")

if (!dir.exists(raw_data_folder)) stop("Error: 'raw' folder not found.")
csv_files <- list.files(raw_data_folder, pattern = "\\.csv$", full.names = TRUE)

walk(csv_files, function(file_path) {
    
    file_basename <- tools::file_path_sans_ext(basename(file_path))
    cat("Plotting 400ms baseline history for:", file_basename, "\n")

    # Create a subfolder named after this session
    session_folder <- file.path(output_zoom_folder, file_basename)
    dir.create(session_folder, showWarnings = FALSE)

    raw_data <- read_csv(file_path, show_col_types = FALSE) %>%
        mutate(row_idx = row_number())

    all_events <- raw_data %>%
        filter(!is.na(event)) %>%
        mutate(
            event_clean = tolower(trimws(event)),
            is_stim = event_clean == "stim",
            is_resp = str_detect(event_clean, "resp|press|response|key")
        )

    resp_indices <- all_events %>% filter(is_resp) %>% slice(1:num_trials) %>% pull(row_idx)
    if(length(resp_indices) == 0) return(NULL)

    walk(fsr_cols, function(fsr_col) {

        if (!fsr_col %in% names(raw_data)) {
            cat("  -> Skipping", fsr_col, ": column not found.\n")
            return(invisible(NULL))
        }

        trial_list     <- list()
        marker_list    <- list()
        green_dot_list <- list()

        for (i in 1:length(resp_indices)) {
            current_resp_idx <- resp_indices[i]
            associated_stim  <- all_events %>% filter(is_stim & row_idx < current_resp_idx) %>% tail(1)
            
            if(nrow(associated_stim) > 0) {
                stim_idx  <- associated_stim$row_idx
                start_idx <- max(1, stim_idx - (pre_stim_s * sampling_rate))
                end_idx   <- min(nrow(raw_data), stim_idx + (post_stim_s * sampling_rate))
                
                segment <- raw_data[start_idx:end_idx, ] %>%
                    mutate(
                        plot_time = (row_number() + (i-1) * (pre_stim_s + post_stim_s) * sampling_rate) / sampling_rate,
                        fsr_val   = .data[[fsr_col]]
                    )
                
                stim_plot_pos   <- segment$plot_time[which(segment$row_idx == stim_idx)]
                peak_idx_in_seg <- which.max(segment$fsr_val)
                peak_plot_pos   <- segment$plot_time[peak_idx_in_seg]
                peak_val        <- segment$fsr_val[peak_idx_in_seg]
                
                dot_sample_offsets <- (ms_offsets / 1000) * sampling_rate
                dots_df <- segment %>%
                    filter(row_idx %in% (stim_idx - dot_sample_offsets))
                
                trial_list[[i]]     <- segment
                marker_list[[i]]    <- data.frame(stim_pos = stim_plot_pos, peak_pos = peak_plot_pos, val = peak_val, trial = i)
                green_dot_list[[i]] <- dots_df
            }
        }

        plot_df    <- bind_rows(trial_list)
        markers    <- bind_rows(marker_list)
        green_dots <- bind_rows(green_dot_list)

        p_baseline <- ggplot(plot_df, aes(x = plot_time, y = fsr_val)) +
            geom_line(color = "black", linewidth = 0.5) +
            geom_vline(data = markers, aes(xintercept = stim_pos), color = "#1565C0", linetype = "dotted", linewidth = 0.8) +
            geom_vline(data = markers, aes(xintercept = peak_pos), color = "#C62828", linetype = "dotted", linewidth = 0.8) +
            geom_point(data = green_dots, aes(x = plot_time, y = fsr_val), color = "#2E7D32", size = 1.8, alpha = 0.8) +
            geom_text(data = markers, aes(x = peak_pos, y = val, label = paste(val, "cts")),
                      color = "#C62828", vjust = -1.2, size = 3, fontface = "bold") +
            geom_text(data = markers, aes(x = stim_pos, y = min(plot_df$fsr_val) - 15, label = paste("Trial", trial)),
                      vjust = 1.5, color = "grey40", size = 3.5) +
            theme_minimal(base_size = 14) +
            labs(
                title    = paste("Extended Pre-Stim Baseline Analysis \u2014", toupper(fsr_col), "\u2014", file_basename),
                subtitle = "Green Dots = every 50ms (up to 400ms) before Stimulus",
                x        = "Sequential Segments (s)",
                y        = "Sensor Counts"
            ) +
            theme(
                panel.grid.minor = element_blank(),
                plot.margin = margin(10, 10, 40, 10)
            )

        save_name <- paste0("extended_baseline_dots_", fsr_col, ".png")
        ggsave(file.path(session_folder, save_name), p_baseline, width = 18, height = 6, dpi = 300)
        cat("  -> Saved:", file.path(file_basename, save_name), "\n")
    })

    cat("\n")
})
