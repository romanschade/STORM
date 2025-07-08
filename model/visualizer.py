import plotly.graph_objects as go
import os

class Visualizer:
    def __init__(self, title: str, x_label: str, y_label: str, target_directory: str) -> None:
        self.title = title # Title of the plot
        self.x_label = x_label # X-Label of the plot
        self.y_label = y_label # Y-Label of the plot
        self.target_directory = target_directory # Directory to save the plot to

        # Shells for future plot data
        self.curve_data = []
        self.curve_names = []
        self.curve_colors = []
        self.curve_styles = []

        # Fond size of the plots
        self.fond_size = 20


    def append_curve_plot(self, data, name: str, color: str, style: str) -> None:
        """Append plot data to the class"""

        self.curve_data.append(data)
        self.curve_names.append(name)
        self.curve_colors.append(color)
        self.curve_styles.append(style)


    def generate_time_labels(self, timesteps: int) -> list[str]:
        """Generate x-axis labels formatted as 'Day x - HH:MM'"""

        # Initialize
        labels = []

        # Compute labels
        for i in range(timesteps):
            total_minutes = i * 15
            day = total_minutes // (24 * 60) + 1
            hour = (total_minutes % (24 * 60)) // 60
            minute = (total_minutes % 60)
            labels.append(f'Day {day} - {hour:02}:{minute:02}')
        return labels


    def generate_curve_plot(self, show: bool = True) -> None:
        """Plot all appended curves using Plotly"""

        # Initialize
        fig = go.Figure()
        timesteps = min(len(c) for c in self.curve_data)
        time_labels = self.generate_time_labels(timesteps=timesteps)

        # Iterate over the list of curve data and other parameters
        for ind_data, ind_name, ind_color, ind_style in zip(self.curve_data, self.curve_names, self.curve_colors,
                                                            self.curve_styles):
            fig.add_trace(go.Scatter(
                x=time_labels[:len(ind_data)],
                y=ind_data,
                mode='lines',
                name=ind_name,
                line=dict(color=ind_color, dash=ind_style, shape='hv')
            ))

        # Dynamically determine spacing for x-axis ticks
        max_ticks = 24  # Maximum number of ticks to display
        step = max(1, timesteps // max_ticks)
        tick_values = list(range(0, timesteps, step))
        tick_text = [time_labels[i] for i in tick_values]

        # Layout customization
        fig.update_layout(
            width=1200,
            height=900,
            title=dict(
                text=self.title,
                font=dict(size=self.fond_size+2)
            ),
            xaxis_title=dict(
                text=self.x_label,
                font=dict(size=self.fond_size)
            ),
            yaxis_title=dict(
                text=self.y_label,
                font=dict(size=self.fond_size)
            ),
            xaxis=dict(
                tickangle=-90,
                tickmode="array",
                tickvals=tick_values,
                ticktext=tick_text,
                tickfont=dict(size=self.fond_size-2)
            ),
            yaxis=dict(
                tickfont=dict(size=self.fond_size-2)
            ),
            template="plotly_white",
            legend=dict(x=0.5, y=-0.3, orientation="h", xanchor="center", font=dict(size=self.fond_size)),
            margin=dict(b=80),
        )

        # Save interactive plot as HTML
        os.makedirs(self.target_directory, exist_ok=True)
        fig.write_html(f"{self.target_directory}/{self.title}.html")

        # Show the interactive plot
        if show:
            fig.show()




