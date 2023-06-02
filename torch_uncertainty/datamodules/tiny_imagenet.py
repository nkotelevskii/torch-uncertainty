# fmt: off
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, List, Optional, Union

import torch.nn as nn
import torchvision.transforms as T
from pytorch_lightning import LightningDataModule
from timm.data.auto_augment import rand_augment_transform
from torch.utils.data import DataLoader, Dataset
from torchvision.datasets import SVHN

from ..datasets import TinyImageNet


# fmt: on
class TinyImageNetDataModule(LightningDataModule):
    num_classes = 200
    num_channels = 3

    def __init__(
        self,
        root: Union[str, Path],
        batch_size: int,
        rand_augment_opt: str = None,
        num_workers: int = 1,
        pin_memory: bool = True,
        persistent_workers: bool = True,
        **kwargs,
    ) -> None:
        super().__init__()
        # TODO: COMPUTE STATS
        if isinstance(root, str):
            root = Path(root)

        self.root: Path = root
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.persistent_workers = persistent_workers
        self.dataset = TinyImageNet
        self.ood_dataset = SVHN

        if rand_augment_opt is not None:
            main_transform = rand_augment_transform(rand_augment_opt, {})
        else:
            main_transform = nn.Identity()

        self.transform_train = T.Compose(
            [
                T.RandomCrop(64, padding=4),
                T.RandomHorizontalFlip(),
                main_transform,
                T.ToTensor(),
                T.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
            ]
        )

        self.transform_test = T.Compose(
            [
                T.Resize(64),
                T.ToTensor(),
                T.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
            ]
        )

    def _verify_splits(self, split: str) -> None:
        if split not in list(self.root.iterdir()):
            raise FileNotFoundError(
                f"a {split} TinyImagenet split was not found in {self.root},"
                f" make sure the folder contains a subfolder named {split}"
            )

    def prepare_data(self) -> None:
        self.ood_dataset(self.root, split="test", download=True)

    def setup(self, stage: Optional[str] = None) -> None:
        if stage == "fit" or stage is None:
            self.train = self.dataset(
                self.root,
                split="train",
                transform=self.transform_train,
            )
            self.val = self.dataset(
                self.root,
                split="val",
                transform=self.transform_test,
            )
        if stage == "test":
            self.test = self.dataset(
                self.root,
                split="val",
                transform=self.transform_test,
            )
            self.ood = self.ood_dataset(
                self.root,
                split="test",
                transform=self.transform_test,
            )

    def train_dataloader(self) -> DataLoader:
        r"""Gets the training dataloader for TinyImageNet.
        Returns:
            DataLoader: TinyImageNet training dataloader.
        """
        return self._data_loader(self.train, shuffle=True)

    def val_dataloader(self) -> DataLoader:
        r"""Gets the validation dataloader for TinyImageNet.
        Returns:
            DataLoader: TinyImageNet validation dataloader.
        """
        return self._data_loader(self.val)

    def test_dataloader(self) -> List[DataLoader]:
        r"""Gets test dataloaders for TinyImageNet.
        Returns:
            List[DataLoader]: TinyImageNet test set (in distribution data) and
            SVHN test split (out-of-distribution data).
        """
        return [self._data_loader(self.test), self._data_loader(self.ood)]

    def _data_loader(
        self, dataset: Dataset, shuffle: bool = False
    ) -> DataLoader:
        return DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=shuffle,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            persistent_workers=self.persistent_workers,
        )

    @classmethod
    def add_argparse_args(
        cls,
        parent_parser: ArgumentParser,
        **kwargs: Any,
    ) -> ArgumentParser:
        p = parent_parser.add_argument_group("datamodule")
        p.add_argument("--root", type=str, default="./data/")
        p.add_argument("--batch_size", type=int, default=256)
        p.add_argument("--num_workers", type=int, default=4)
        p.add_argument(
            "--rand_augment", dest="rand_augment_opt", type=str, default=None
        )
        return parent_parser
