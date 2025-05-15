import threading
from capture import capture_identifiers, capture_queue
from gui import IdentifierApp

def main():
    tcap = threading.Thread(target=capture_identifiers, args=(capture_queue,))
    tcap.daemon=True
    tcap.start()

    IdentifierApp().run()

if __name__=="__main__":
    main()
