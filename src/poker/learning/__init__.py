from poker.learning.actions import (
	LearningActionEncoder,
	LearningActionSpace,
)
from poker.learning.dataset import (
	LearningDatasetAnalyzer,
	LearningDatasetCapture,
	LearningDatasetWriter,
)
from poker.learning.import_teacher import TeacherRecordImporter
from poker.learning.observation import (
	LearningObservation,
	LearningObservationEncoder,
)
from poker.learning.sample import LearningSample, LearningSampleBuilder

__all__ = [
	"LearningActionEncoder",
	"LearningActionSpace",
	"LearningDatasetAnalyzer",
	"LearningDatasetCapture",
	"LearningDatasetWriter",
	"DatasetGenerationConfig",
	"DatasetGenerationResult",
	"LearningDatasetGenerator",
	"LearningObservation",
	"LearningObservationEncoder",
	"LearningSample",
	"LearningSampleBuilder",
	"TeacherRecordImporter",
]


def __getattr__(name):
    # Dataset generation loads agents and their optional PyTorch dependency.
    # Importing the pure HUD contract must not initialize that runtime.
    if name in {"DatasetGenerationConfig", "DatasetGenerationResult", "LearningDatasetGenerator"}:
        from importlib import import_module

        value = getattr(import_module("poker.learning.generation"), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
