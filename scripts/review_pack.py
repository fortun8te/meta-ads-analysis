#!/usr/bin/env python3
"""Compatibility alias for analyze_meta: JSON analysis only, no HTML output."""
if __package__:
    from .analyze_meta import analyze, check_ids, local_path, main, present
else:
    from analyze_meta import analyze, check_ids, local_path, main, present

if __name__ == '__main__':
    main()
