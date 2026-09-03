library(dplyr)
library(readr)
library(ggplot2)
library(purrr)
library(tidyr)
library(stringr)

# --- Paths ---
raw_data_folder    <- "raw"
output_plot_folder <- "Stim Response Plots"
dir.create(output_plot_folder, showWarnings = FALSE)

fsr_cols <- c("fsr1", "fsr2", "fsr3", "fsr4")

if (!dir.exists(raw_data_folder)) stop("Error: 'raw' folder not found.")
csv_files <- list.files(raw_data_folder, pattern = "\\.csv$", full.names = TRUE)
if (length(csv_files) == 0) stop("No CSV files found in 'raw' folder.")
cat("Found", length(csv_files), "file(s) to process...\n\n")

walk(csv_files, function(file_path) {

    file_basename <- tools::file_path_sans_ext(basename(file_path))
    cat("Processing:", basename(file_path), "\n")

    # Create a subfolder named after this session
    session_folder <- file.path(output_plot_folder, file_basename)
    dir.create(session_folder, showWarnings = FALSE)

    raw_data <- read_csv(
        file_path,
        col_types      = cols(.default = col_character()),
        show_col_types = FALSE
    ) %>%
        type_convert() %>%
        mutate(row_idx = row_number())

    if ("t_perf" %in% names(raw_data)) {
        raw_data <- raw_data %>% mutate(t_sec = as.numeric(t_perf))
    } else if ("ts_perf" %in% names(raw_data)) {
        raw_data <- raw_data %>% mutate(t_sec = as.numeric(ts_perf))
    } else {
        raw_data <- raw_data %>% mutate(t_sec = row_idx / 200)
        cat("  -> No t_perf column; estimating time at 200 Hz.\n")
    }

    raw_data <- raw_data %>%
        mutate(across(starts_with("fsr"), ~ . - 255.0))

    event_types <- raw_data %>%
        filter(!is.na(event), trimws(event) != "") %>%
        pull(event) %>% unique() %>% tolower() %>% trimws()
    cat("  -> Event types found:", paste(event_types, collapse = ", "), "\n")

    stim_data <- raw_data %>%
        filter(tolower(trimws(coalesce(event, ""))) == "stim") %>%
        mutate(event_type = "Stim") %>%
        arrange(t_sec) %>%
        mutate(event_num = row_number())

    response_data <- raw_data %>%
        filter(str_detect(tolower(trimws(coalesce(event, ""))), "resp|press|response|key")) %>%
        mutate(event_type = "Response") %>%
        arrange(t_sec) %>%
        mutate(event_num = row_number())

    cat("  -> Stim rows:", nrow(stim_data), "| Response rows:", nrow(response_data), "\n")

    if (nrow(stim_data) == 0 && nrow(response_data) == 0) {
        cat("  -> Skipping: no stim or response events found.\n\n")
        return(invisible(NULL))
    }

    walk(fsr_cols, function(fsr_col) {

        matched_col <- names(raw_data)[tolower(names(raw_data)) == fsr_col]
        if (length(matched_col) == 0) {
            cat("  -> Skipping", fsr_col, ": column not found.\n")
            return(invisible(NULL))
        }

        combined <- bind_rows(stim_data, response_data) %>%
            arrange(t_sec) %>%
            select(t_sec, event_type, all_of(matched_col)) %>%
            rename(fsr_value = all_of(matched_col))

        y_min    <- floor(min(combined$fsr_value, na.rm = TRUE) / 5) * 5
        y_max    <- ceiling(max(combined$fsr_value, na.rm = TRUE) / 5) * 5
        y_breaks <- seq(y_min, y_max, by = 5)

        p <- ggplot(combined,
                    aes(x = t_sec, y = fsr_value, colour = event_type, shape = event_type)) +
            geom_line(aes(group = event_type), linewidth = 0.6, alpha = 0.4) +
            geom_point(size = 1.8, alpha = 0.85) +
            geom_hline(yintercept = 0, linetype = "dashed", colour = "grey60", linewidth = 0.4) +
            scale_y_continuous(breaks = y_breaks, minor_breaks = NULL) +
            coord_cartesian(ylim = c(-10, y_max)) +
            scale_colour_manual(
                values = c("Stim" = "#1565C0", "Response" = "#C62828"),
                name   = "Event type"
            ) +
            scale_shape_manual(
                values = c("Stim" = 16, "Response" = 17),
                name   = "Event type"
            ) +
            labs(
                title    = paste(toupper(fsr_col), "\u2014 Stim vs Response Events \u2014", file_basename),
                subtitle = paste0(
                    "Blue = ", toupper(fsr_col), " value at each stim event. ",
                    "Red = ", toupper(fsr_col), " value at each response/press event. ",
                    "Values corrected by \u2212255 offset."
                ),
                x = "Time (s)",
                y = paste("Corrected", toupper(fsr_col), "value")
            ) +
            theme_minimal(base_size = 14) +
            theme(
                plot.title       = element_text(face = "bold", hjust = 0),
                plot.subtitle    = element_text(colour = "grey40", size = 10),
                legend.position  = "bottom",
                panel.grid.major = element_line(colour = "grey88"),
                panel.grid.minor = element_blank()
            )

        out_file <- file.path(session_folder, paste0(fsr_col, "_stim_vs_response.png"))
        ggsave(out_file, p, width = 16, height = 9, dpi = 300)
        cat("  -> Saved:", file.path(file_basename, basename(out_file)), "\n")
    })

    cat("\n")
})

cat("All done. Outputs are in '", output_plot_folder, "/'.\n", sep = "")
