from datasets.vertebral_dataset import VertebralDataset
from models.mlp import MLPParams, test_model
from models.quant.enums import ActivationModule, QMode

p = MLPParams(
    in_layer_height=VertebralDataset.input_size,
    in_bitwidth=32,
    out_height=VertebralDataset.output_size,
    hidden_height=16,
    hidden_bitwidth=32,
    model_layers=3,
    learning_rate=0.01,
    activation=ActivationModule.RELU,
    epochs=15,
    dropout_rate=0.2,
    quantization_mode=QMode.DET,
)
train_loader, test_loader = VertebralDataset.get_dataloaders(batch_size=16)

test_model(p, train_loader, test_loader, verbose=2)
