from .vita_loader import sweep_before_load, attempt_additional_cleaning
from binaryninja import PluginCommand, BinaryView

def is_symbols_injected(bv: BinaryView) -> bool:
    """
    Check persistant(.bndb) faux `VitaELF_Injected` symbol.
    This prevents running additional optional features until symbols have been injected.
    """
    return bv.get_symbol_by_raw_name("VitaELF_Injected") is not None


PluginCommand.register(
    "PSVitaLoader\\1. VitaELF: Inject Symbols",
    "Injects resolved NID symbols into the ARMv7 BinaryView.",
    sweep_before_load
)

PluginCommand.register(
    "PSVitaLoader\[Experimental] Attempt Additional Cleaning",
    "Likely to give better results, removes non t2(base instruction) functions, re-runs linsweep, then removes any mis-identified functions where known data/variables exists.",
    attempt_additional_cleaning,
    is_symbols_injected
)
