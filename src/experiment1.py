import logging
import os

import pandas as pd
import plotly.express as px

from src.datasets.cifar10_dataset import CIFAR10Dataset, MiniCIFAR10Dataset
from src.datasets.dataset import CnnDataset
from src.datasets.mnist_dataset import MiniMNIST32x32Dataset, MNIST32x32Dataset
from src.models.builders.architecture_builder import ArchitectureBuilder, BuilderParams
from src.models.builders.LeNet5_builder import LeNet5Builder
from src.models.builders.VGGNet_builder import VGGNetBuilder
from src.models.compression.enums import Activation, NNParamsCompMode
from src.models.eval import NNArchitectureEvaluator
from src.models.nn import ActivationParams
from src.reporting import get_reporting_folder

logger = logging.getLogger(__name__)


def get_prefix(path: str | None = None) -> str:
    return os.path.join(get_reporting_folder(path), "experiment1_")


full_dataset_architecture_pairs: list[
    tuple[type[CnnDataset], type[ArchitectureBuilder]]
] = [
    (MNIST32x32Dataset, LeNet5Builder),
    (CIFAR10Dataset, VGGNetBuilder),
]
mini_dataset_architecture_pairs: list[
    tuple[type[CnnDataset], type[ArchitectureBuilder]]
] = [
    (MiniMNIST32x32Dataset, LeNet5Builder),
    (MiniCIFAR10Dataset, VGGNetBuilder),
]


def run_experiment1(
    output_folder: str,
    evaluations: int = 1,
    epochs: int = 1,
    patience: int = 1,
    plot: bool = False,
    dataset_size: str = "mini",
):
    if dataset_size == "full":
        pairs = full_dataset_architecture_pairs
    elif dataset_size == "mini":
        pairs = mini_dataset_architecture_pairs

    for DatasetCls, BuilderCls in pairs:
        df = run(DatasetCls, BuilderCls, epochs, patience, evaluations)

        df.to_csv(os.path.join(output_folder, "results.csv"), index=False)

        if plot:
            plot_results(df, output_folder)

        logger.info(f"Experiment 1 on dataset {DatasetCls.__name__} completed")

    logger.info("Experiment 1 completed")


def plot_results(df: pd.DataFrame, folder: str):
    fig = px.parallel_categories(
        df.sort_values("mean", ascending=False),
        dimensions=[
            "conv_activation",
            "conv_compression",
            "mean",
        ],
        color_continuous_scale=px.colors.sequential.Inferno,
    )
    fig.write_html(os.path.join(folder + "mean_accuracy.html"))
    fig.show()

    fig = px.parallel_categories(
        df.sort_values("best", ascending=False),
        dimensions=[
            "conv_activation",
            "conv_compression",
            "best",
        ],
        color_continuous_scale=px.colors.sequential.Inferno,
    )
    fig.write_html(os.path.join(folder + "best_accuracy.html"))
    fig.show()


def run(
    DatasetCls: type[CnnDataset],
    BuilderCls: type[ArchitectureBuilder],
    epochs: int = 1,
    patience: int = 1,
    evaluate_times: int = 1,
) -> pd.DataFrame:
    datapoints = []

    logger.info(
        f"Running experiment on {DatasetCls.__name__} with {BuilderCls.__name__} architecture..."
    )

    # Run training
    for activation in Activation:
        for conv_compression in NNParamsCompMode:

            params = BuilderParams(
                conv_compression=conv_compression,
                conv_bitwidth=4,
                conv_activation=ActivationParams(activation),
                fc_compression=conv_compression,
                fc_bitwidth=4,
                fc_activation=ActivationParams(activation),
                DatasetCls=DatasetCls,
                epochs=epochs,
                early_stop_patience=patience,
                batch_size=DatasetCls.batch_size,
                evaluate_times=evaluate_times,
            )
            stats = evaluate_compression(BuilderCls(params))
            if stats is not None:
                datapoints.append(stats)

    logger.info(
        f"Collected {len(datapoints)} datapoints for {DatasetCls.__name__} dataset"
    )

    return pd.DataFrame(datapoints)


def evaluate_compression(builder: ArchitectureBuilder) -> dict | None:
    params = builder.get_params()
    evaluator = NNArchitectureEvaluator(params.train)

    logger.info(f"Evaluating {builder.name}")
    logger.info(
        f"{builder.p.conv_compression.name=}, {builder.p.conv_activation.activation.name=}"
    )
    logger.info(
        f"{builder.p.fc_compression.name=}, {builder.p.fc_activation.activation.name=}"
    )
    try:
        stats = evaluator.evaluate_accuracy(params, times=builder.p.evaluate_times)
    except Exception as e:
        logger.error(f"Failed to evaluate: {e}")
        return None

    return {
        # Properties
        "architecture": builder.name,
        "dataset": builder.p.DatasetCls.__name__,
        "conv_compression": builder.p.conv_compression.name,
        "conv_activation": builder.p.conv_activation.activation.name,
        "fc_compression": builder.p.fc_compression.name,
        "fc_activation": builder.p.fc_activation.activation.name,
        # Stats
        "best": stats["max"],
        "mean": stats["mean"],
        "accuracies": stats["accuracies"],
        "cost": evaluator.evaluate_complexity(params),
    }
