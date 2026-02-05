from utils.cache import cache_stats
stats = cache_stats()
print('offline', stats.get('offline'))
print('reason', stats.get('offline_reason'))
print('auto_resume_in', stats.get('auto_resume_in'))
