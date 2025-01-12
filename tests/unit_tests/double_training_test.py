import unittest
import torch
from super_gradients import Trainer
from super_gradients.common.object_names import Models
from super_gradients.training import models
from super_gradients.training.dataloaders.dataloaders import classification_test_dataloader
from super_gradients.training.metrics import Accuracy


class CallTrainTwiceTest(unittest.TestCase):
    """
    CallTrainTwiceTest

    Purpose is to call train twice and see nothing crashes. Should be ran with available GPUs (when possible)
    so when calling train again we see there's no change in the model's device.
    """

    def test_call_train_twice(self):
        trainer = Trainer("external_criterion_test")
        dataloader = classification_test_dataloader(batch_size=10)

        model = models.get(Models.RESNET18, num_classes=5)
        train_params = {
            "max_epochs": 2,
            "lr_updates": [1],
            "lr_decay_factor": 0.1,
            "lr_mode": "StepLRScheduler",
            "lr_warmup_epochs": 0,
            "initial_lr": 0.1,
            "loss": torch.nn.CrossEntropyLoss(),
            "optimizer": "SGD",
            "optimizer_params": {"weight_decay": 1e-4, "momentum": 0.9},
            "train_metrics_list": [Accuracy()],
            "valid_metrics_list": [Accuracy()],
            "metric_to_watch": "Accuracy",
            "greater_metric_to_watch_is_better": True,
        }
        trainer.train(model=model, training_params=train_params, train_loader=dataloader, valid_loader=dataloader)
        trainer.train(model=model, training_params=train_params, train_loader=dataloader, valid_loader=dataloader)


if __name__ == "__main__":
    unittest.main()
