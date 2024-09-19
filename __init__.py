from .vita_loader import sweep_before_load
from binaryninja import PluginCommand

PluginCommand.register(
    "VitaELF: Inject Symbols",
    "Injects resolved NID symbols into the ARMv7 BinaryView.",
    sweep_before_load
)
