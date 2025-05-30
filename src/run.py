import logging

import pandas as pd
from pymoo.optimize import minimize

from src.constants import SEED
from src.datasets.dataset import CnnDataset, MlpDataset
from src.models.nn import save_model
from src.nas.cnn_nas_problem import CnnNasProblem
from src.nas.mlp_nas_problem import MlpNasProblem
from src.nas.nas_params import NasParams
from src.nas.plot import hist_accuracies, plot_pareto_front

logger = logging.getLogger(__name__)


def run_nas_pipeline(
    dataset: str,
    epochs: int | None,
    batch_size: int | None,
    population_size: int | None,
    offspring_count: int | None,
    generations: int,
    store_models: bool,
    output_file: str | None,
    histogram: str | None,
    pareto: str | None,
):
    # TODO: Parametrize other parameters too

    CnnDatasetClass = try_get_cnn_dataset(dataset)
    MlpDatasetClass = try_get_mlp_dataset(dataset)

    if CnnDatasetClass:
        nas_params = NasParams(
            batch_size=batch_size,
            epochs=epochs or 1,
            patience=5,
            amount_of_evaluations=1,
            population_size=population_size or 10,
            population_offspring_count=offspring_count or 4,
            algorithm_generations=generations,
            population_store_file=output_file
            or (CnnDatasetClass.__name__ + "_population.csv"),
        )
        problem = CnnNasProblem(nas_params, CnnDatasetClass)

    elif MlpDatasetClass:
        nas_params = NasParams(
            batch_size=batch_size,
            epochs=epochs or 10,
            patience=5,
            amount_of_evaluations=1,
            population_size=population_size or 20,
            population_offspring_count=offspring_count or 8,
            algorithm_generations=generations,
            population_store_file=output_file
            or MlpDatasetClass.__name__ + "_population.csv",
        )
        problem = MlpNasProblem(nas_params, MlpDatasetClass)

    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    logger.info("Starting NAS")
    df = run_nas(problem, nas_params)
    logger.info("NAS has finished")

    if store_models:
        for chromosome, (accuracy, model) in problem.best_architecture.items():
            if chromosome in map(tuple, df["Chromosome"].values):
                chromosome_str = "-".join(map(str, chromosome))
                accuracy_str = str(round(accuracy, 4))
                save_model(
                    model,
                    f"{problem.DatasetCls.__name__}_{accuracy_str}_{chromosome_str}.pt",
                    override=True,
                )

    if histogram is not None:
        hist_fig = hist_accuracies(df["Accuracy"])
        hist_fig.savefig(histogram)

    if pareto is not None:
        pareto_fig = plot_pareto_front(df["Accuracy"], df["Complexity"])
        pareto_fig.savefig(pareto)

    print(df.to_string(index=False, columns=["Accuracy", "Complexity", "Chromosome"]))


def try_get_cnn_dataset(dataset: str) -> type[CnnDataset] | None:
    match dataset:
        case "mnist":
            from src.datasets.mnist_dataset import MNISTDataset

            return MNISTDataset
        case "mini-mnist":
            from src.datasets.mnist_dataset import MiniMNISTDataset

            return MiniMNISTDataset
        case "cifar10":
            from src.datasets.cifar10_dataset import CIFAR10Dataset

            return CIFAR10Dataset
        case "mini-cifar10":
            from src.datasets.cifar10_dataset import MiniCIFAR10Dataset

            return MiniCIFAR10Dataset
        case _:
            return None


def try_get_mlp_dataset(dataset: str) -> type[MlpDataset] | None:
    match dataset:
        case "vertebral":
            from src.datasets.vertebral_dataset import VertebralDataset

            return VertebralDataset
        case "cardio":
            from src.datasets.cardio_dataset import CardioDataset

            return CardioDataset
        case "breast-cancer":
            from src.datasets.breast_cancer_dataset import BreastCancerDataset

            return BreastCancerDataset
        case _:
            return None


def run_nas(
    problem: CnnNasProblem | MlpNasProblem, nas_params: NasParams
) -> pd.DataFrame:
    algorithm = nas_params.get_algorithm()
    termination = nas_params.get_termination()

    res = minimize(problem, algorithm, verbose=True, seed=SEED, termination=termination)

    if nas_params.population_store_file is not None:
        nas_params.store_population(res, nas_params.population_store_file)

    df = problem.result_as_df(res)
    return df
