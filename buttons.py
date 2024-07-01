class KeyBoardButton:

    @classmethod
    def require_login(cls):
        return {
            'one_time_keyboard': True,
            'keyboard': [[
                {
                    'request_contact': True,
                    'text': 'הזדהות'
                }
            ]]
        }
