# BF/context_processors.py
"""
Context processor to detect which domain the user is visiting
and provide site-specific configuration to templates.
"""

from django.conf import settings


def site_info(request):
    """
    Detect the current domain and return site-specific information.
    This makes site info available in all templates automatically.
    """
    host = request.get_host()
    
    # Detect which site based on domain
    current_site = settings.DEFAULT_SITE
    
    if 'arthurflix' in host.lower():
        current_site = 'arthurflix'
    elif 'bollyfun' in host.lower():
        current_site = 'bollyfun'
    
    # Get site configuration
    site_config = settings.SITE_DOMAINS.get(
        current_site, 
        settings.SITE_DOMAINS[settings.DEFAULT_SITE]
    )
    
    return {
        'SITE_NAME': site_config['name'],
        'SITE_DOMAIN': site_config['domain'],
        'SITE_LOGO': site_config['logo'],
        'SITE_PRIMARY_COLOR': site_config['primary_color'],
        'CURRENT_SITE_KEY': current_site,
    }